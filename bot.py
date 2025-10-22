"""Telegram orchestrator bot for multi-agent content generation.

This script is intended to be run inside Google Colab. Install the
requirements listed in `requirements.txt`, set the environment variables
`OPENAI_API_KEY` and `TELEGRAM_BOT_TOKEN`, and run the script to start the
bot.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (Application, ApplicationBuilder, CommandHandler,
                          ContextTypes, MessageHandler, filters)


logger = logging.getLogger(__name__)


STRATEGIST_SYSTEM_PROMPT = (
    "Ты — стратег высокого уровня. Анализируй пользовательский запрос и "
    "формируй подробный, иерархический план работы с крупными разделами, "
    "подзадачами и ожидаемыми результатами. Описывай этапы так, чтобы их было "
    "удобно передавать менеджеру для дальнейшей декомпозиции."
)

MANAGER_SYSTEM_PROMPT = (
    "Ты — менеджер проекта. Тебе передали исходный пользовательский запрос и "
    "план от стратега. Твоя задача — пошагово ставить задачи джуниору, "
    "анализировать их выполнение и повторять цикл до полного закрытия цели. "
    "\n\n"
    "* Всегда отвечай в формате JSON.\n"
    "* Для постановки задач используй форму: {\"status\": \"task\", \"task_id\": int, "
    "\"instructions\": str, \"notes\": str}.\n"
    "* После ревью результата джуниора ты можешь поставить следующую задачу, "
    "добавить уточнения или завершить работу.\n"
    "* Когда работа полностью завершена, верни JSON вида: {\"status\": "
    "\"final\", \"summary\": str, \"deliverable\": str}.\n"
    "* Если необходимо попросить переработку задачи, сформулируй новую задачу с "
    "новым `task_id`.\n"
    "* Помни, что итоговый документ может быть очень большим. Планируй работу "
    "так, чтобы собирать материал по частям."
)

JUNIOR_SYSTEM_PROMPT = (
    "Ты — исполнитель уровня junior. Получаешь от менеджера чёткие "
    "инструкции и создаёшь содержательный текст. Всегда отвечай в формате JSON: "
    "{\"status\": \"done\", \"content\": str, \"notes\": str}. Следуй тону и стилю "
    "задачи, уделяй внимание деталям и полноте."
)

MAX_MANAGER_ITERATIONS = 30


@dataclass
class TaskResult:
    task_id: int
    instructions: str
    content: str
    notes: Optional[str] = None


def extract_json_object(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from a text response."""
    text = text.strip()

    # Unwrap code fences if present
    code_fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_fence_match:
        candidate = code_fence_match.group(1)
    else:
        # Try to find the first {...} block
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        candidate = brace_match.group(0) if brace_match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
        logger.error("Failed to parse JSON from manager/junior response: %s", text)
        raise ValueError("Agent response is not valid JSON") from exc


class OpenAIAgent:
    def __init__(self, client: OpenAI, model: str, system_prompt: str):
        self.client = client
        self.model = model
        self.system_prompt = system_prompt

    def run(self, user_content: str, conversation: Optional[List[Dict[str, str]]] = None) -> str:
        """Call the OpenAI Responses API for a single turn."""
        history: List[Dict[str, str]] = conversation[:] if conversation else []
        input_messages = [{"role": "system", "content": self.system_prompt}]
        input_messages.extend(history)
        input_messages.append({"role": "user", "content": user_content})

        response = self.client.responses.create(
            model=self.model,
            input=input_messages,
        )

        return collect_response_text(response)


def collect_response_text(response: Any) -> str:
    """Extract text from an OpenAI Responses API payload."""
    if hasattr(response, "output_text"):
        return response.output_text

    parts: List[str] = []
    for item in getattr(response, "output", []):
        if item.type != "message":
            continue
        for content in getattr(item, "content", []):
            if content.type == "text":
                parts.append(content.text)
    return "".join(parts)


class Orchestrator:
    def __init__(self, client: OpenAI):
        self.client = client
        self.strategist = OpenAIAgent(client, "gpt-5", STRATEGIST_SYSTEM_PROMPT)
        self.manager = OpenAIAgent(client, "gpt-4.1", MANAGER_SYSTEM_PROMPT)
        self.junior = OpenAIAgent(client, "gpt-5-nano", JUNIOR_SYSTEM_PROMPT)

    async def create_plan(self, prompt: str) -> str:
        return await asyncio.to_thread(self.strategist.run, prompt)

    async def execute_plan(self, prompt: str, plan: str) -> Tuple[str, List[TaskResult]]:
        manager_history: List[Dict[str, str]] = []
        manager_input = (
            "Пользовательский запрос:\n" + prompt + "\n\n" +
            "План от стратега:\n" + plan + "\n\n" +
            "Начни с постановки первой задачи. Помни про JSON-формат."
        )

        accumulated_results: List[TaskResult] = []

        for iteration in range(1, MAX_MANAGER_ITERATIONS + 1):
            manager_reply_text = await asyncio.to_thread(
                self.manager.run,
                manager_input,
                manager_history,
            )
            manager_history.append({"role": "user", "content": manager_input})
            manager_history.append({"role": "assistant", "content": manager_reply_text})
            manager_payload = extract_json_object(manager_reply_text)

            status = manager_payload.get("status")
            if status == "final":
                summary = manager_payload.get("summary", "")
                deliverable = manager_payload.get("deliverable", "")
                final_text = summary + "\n\n" + deliverable if summary else deliverable
                return final_text.strip(), accumulated_results

            if status != "task":
                raise ValueError(
                    f"Manager returned unexpected status: {status!r}. Full payload: {manager_payload}"
                )

            task_id = manager_payload.get("task_id", iteration)
            instructions = manager_payload.get("instructions", "")
            notes = manager_payload.get("notes", "")

            junior_input = (
                f"Task ID: {task_id}\n" +
                f"Пользовательский запрос: {prompt}\n\n" +
                f"План: {plan}\n\n" +
                f"Инструкции менеджера: {instructions}\n\n" +
                "Подготовь полный развёрнутый ответ."
            )

            junior_reply_text = await asyncio.to_thread(self.junior.run, junior_input)
            junior_payload = extract_json_object(junior_reply_text)

            if junior_payload.get("status") != "done":
                raise ValueError(
                    f"Junior failed to finish task {task_id}: {junior_payload}"
                )

            content = junior_payload.get("content", "")
            content_notes = junior_payload.get("notes")
            accumulated_results.append(
                TaskResult(task_id=task_id, instructions=instructions, content=content, notes=content_notes)
            )

            manager_follow_up = (
                f"Результат по задаче {task_id}:\n{content}\n\n"
                f"Примечания джуниора: {content_notes or 'нет'}"
            )
            manager_history.append({"role": "user", "content": manager_follow_up})
            manager_input = "Проанализируй результат и действуй дальше."

        raise RuntimeError(
            "Достигнут лимит итераций менеджера. Вероятно, задача требует вмешательства оператора."
        )


class TelegramBot:
    def __init__(self) -> None:
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.openai_api_key or not self.telegram_token:
            raise RuntimeError(
                "Both OPENAI_API_KEY and TELEGRAM_BOT_TOKEN environment variables must be set."
            )

        self.client = OpenAI(api_key=self.openai_api_key)
        self.orchestrator = Orchestrator(self.client)

    def build_application(self) -> Application:
        application = (
            ApplicationBuilder()
            .token(self.telegram_token)
            .post_init(self._post_init)
            .build()
        )
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        return application

    async def _post_init(self, application: Application) -> None:
        logger.info("Bot started as %s", application.bot.username)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Привет! Отправь мне задачу, и я организую работу стратега, менеджера и джуниора."
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return

        prompt = update.message.text
        chat_id = update.message.chat_id

        await update.message.reply_text("Стратег анализирует задачу...")
        try:
            plan = await self.orchestrator.create_plan(prompt)
            await context.bot.send_message(chat_id, f"План работы:\n{plan}")

            await context.bot.send_message(chat_id, "Менеджер приступает к выполнению плана...")
            final_text, tasks = await self.orchestrator.execute_plan(prompt, plan)

            progress_lines = []
            for task in tasks:
                block = (
                    f"<b>Задача {task.task_id}</b>\n"
                    f"<i>Инструкции:</i> {html.escape(task.instructions)}\n"
                    f"<i>Результат:</i> {html.escape(task.content)}\n"
                )
                if task.notes:
                    block += f"<i>Заметки:</i> {html.escape(task.notes)}\n"
                progress_lines.append(block)

            if progress_lines:
                await context.bot.send_message(
                    chat_id,
                    "\n\n".join(progress_lines),
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )

            await context.bot.send_message(chat_id, "Финальный результат готов:")
            await context.bot.send_message(chat_id, final_text)
        except Exception as exc:  # pragma: no cover - runtime error reporting
            logger.exception("Failed to process request")
            await context.bot.send_message(
                chat_id,
                f"Во время обработки запроса произошла ошибка: {exc}",
            )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = TelegramBot()
    application = bot.build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
