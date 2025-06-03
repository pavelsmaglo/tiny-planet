import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

# If available, import llama_cpp to run a local LLM. Attempt to install the
# package automatically if it is missing. If installation fails we keep Llama as
# None so the GUI can display an informative error message.
try:
    from llama_cpp import Llama
except ImportError:  # attempt automatic installation
    import subprocess
    import sys
    Llama = None
    try:
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "llama-cpp-python",
        ])
        from llama_cpp import Llama  # retry after installation
    except Exception as e:
        print("Failed to install llama-cpp-python:", e)
        print("Install Visual Studio Build Tools and CMake, then run:\n"
              "pip install llama-cpp-python")


class LLMApp:
    def __init__(self, master):
        self.master = master
        master.title("LLM Task Runner")

        tk.Label(master, text="Prompt:").grid(row=0, column=0, sticky='w')
        self.prompt_entry = tk.Entry(master, width=60)
        self.prompt_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(master, text="Folder:").grid(row=1, column=0, sticky='w')
        self.folder_entry = tk.Entry(master, width=60)
        self.folder_entry.grid(row=1, column=1, padx=5, pady=5)
        tk.Button(master, text="Browse", command=self.browse_folder).grid(row=1, column=2)

        tk.Label(master, text="Model path:").grid(row=2, column=0, sticky='w')
        self.model_entry = tk.Entry(master, width=60)
        self.model_entry.grid(row=2, column=1, padx=5, pady=5)
        self.model_entry.insert(0, r"C:\Users\Pavel\Desktop\Patronus\gemma-3-12b-it-Q4_K_M.gguf")
        tk.Button(master, text="Browse", command=self.browse_model).grid(row=2, column=2)

        tk.Label(master, text="Output format:").grid(row=3, column=0, sticky='w')
        self.format_var = tk.StringVar(value='text')
        tk.Radiobutton(master, text="Text", variable=self.format_var, value='text').grid(row=3, column=1, sticky='w')
        tk.Radiobutton(master, text="Docx", variable=self.format_var, value='docx').grid(row=3, column=1)

        tk.Button(master, text="Start", command=self.start_loop).grid(row=4, column=1, pady=10)

        self.llm = None

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder)

    def browse_model(self):
        path = filedialog.askopenfilename(filetypes=[('GGUF files', '*.gguf'), ('All files', '*.*')])
        if path:
            self.model_entry.delete(0, tk.END)
            self.model_entry.insert(0, path)

    def load_model(self):
        if Llama is None:
            messagebox.showerror("Error", "llama_cpp library not installed")
            return False
        self.model_path = self.model_entry.get()
        if not os.path.isfile(self.model_path):
            messagebox.showerror("Error", f"Model not found: {self.model_path}")
            return False
        if self.llm is None:
            self.llm = Llama(model_path=self.model_path)
        return True

    def run_llm(self, prompt):
        if not self.load_model():
            return ""
        # Basic usage of llama_cpp
        result = self.llm(prompt, max_tokens=256)
        if isinstance(result, dict) and 'choices' in result:
            return result['choices'][0]['text']
        return str(result)

    def process_folder(self, folder, prompt):
        files = list(Path(folder).glob('*'))
        results = []
        for f in files:
            file_prompt = prompt
            if f.suffix.lower() == '.txt':
                try:
                    content = f.read_text(encoding='utf-8')
                    file_prompt = f"{prompt}\n{content}"
                except Exception:
                    pass
            response = self.run_llm(file_prompt)
            results.append(f"{f.name}:\n{response}\n")
        return ''.join(results)

    def save_output(self, text):
        folder = self.folder_entry.get()
        if not folder:
            folder = os.getcwd()
        output_path = Path(folder) / 'llm_output'
        output_path.mkdir(exist_ok=True)
        if self.format_var.get() == 'docx':
            try:
                from docx import Document
            except ImportError:
                messagebox.showerror("Error", "python-docx not installed")
                return
            doc = Document()
            doc.add_paragraph(text)
            file_path = output_path / 'result.docx'
            doc.save(file_path)
        else:
            file_path = output_path / 'result.txt'
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
        messagebox.showinfo("Saved", f"Result saved to {file_path}")

    def start_loop(self):
        prompt = self.prompt_entry.get()
        folder = self.folder_entry.get()
        if not prompt:
            messagebox.showwarning("Warning", "Prompt is empty")
            return
        if not folder:
            messagebox.showwarning("Warning", "Folder not selected")
            return
        while True:
            processed = self.process_folder(folder, prompt)
            self.save_output(processed)
            if not messagebox.askyesno("Continue", "Run again?"):
                break


def main():
    root = tk.Tk()
    app = LLMApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
