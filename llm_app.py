import os
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

# Use Ollama to run the local LLM. Install the `ollama` package on first run if
# needed so that the GUI can communicate with the local Ollama server.
try:
    import ollama
except ImportError:
    import sys
    try:
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "ollama",
        ])
        import ollama  # retry after installation
    except Exception as e:  # keep a stub so we can report the error in the UI
        ollama = None
        print("Failed to install the ollama package:", e)
        print("Please install it manually with 'pip install ollama'")


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

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder)

    def browse_model(self):
        path = filedialog.askopenfilename(filetypes=[('Model files', '*.gguf'), ('All files', '*.*')])
        if path:
            self.model_entry.delete(0, tk.END)
            self.model_entry.insert(0, path)

    def ensure_model_available(self, model_or_path: str) -> str | None:
        """Return an Ollama model name, creating one from a local path if needed."""
        if not model_or_path:
            messagebox.showwarning("Warning", "Model name is empty")
            return None

        # If the value looks like a path to a local GGUF file, create a temporary
        # model for it. Ollama's API identifies models by name and can't accept a
        # raw file path directly.
        if os.path.isfile(model_or_path):
            # Use the file name without extension as the model name
            name = Path(model_or_path).stem
            modelfile_contents = f"FROM {model_or_path}"
            with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
                tmp.write(modelfile_contents)
                tmp_path = tmp.name
            try:
                # Ollama's Python package changed parameter names across versions.
                # Attempt the newer API first and fall back if necessary.
                try:
                    ollama.create(model=name, path=tmp_path)
                except TypeError:
                    ollama.create(name=name, modelfile=tmp_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to register model: {e}")
                os.unlink(tmp_path)
                return None
            os.unlink(tmp_path)
            return name

        return model_or_path

    def load_model(self):
        if ollama is None:
            messagebox.showerror("Error", "The 'ollama' package is not available")
            return False
        self.model_name = self.ensure_model_available(self.model_entry.get().strip())
        return bool(self.model_name)

    def run_llm(self, prompt):
        if not self.load_model():
            return ""
        try:
            result = ollama.generate(model=self.model_name, prompt=prompt)
            if isinstance(result, dict):
                return result.get('response', '')
            return str(result)
        except Exception as e:
            messagebox.showerror("Error", f"Ollama failed: {e}")
            return ""

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
