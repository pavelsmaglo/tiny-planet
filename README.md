# Tiny Planet LLM App

This repository includes a small Tkinter-based application to run a local language model on Windows using [Ollama](https://ollama.ai/). The GUI lets you enter a prompt, choose a folder to process, select the model name (or path) and pick an output format.

## Requirements
- Python 3.10 or newer
- `python-docx` if you want to save output as `.docx`

The application will attempt to install the `ollama` Python package automatically
the first time it is launched so it can communicate with the local Ollama server.
Make sure Ollama 0.8.0 or newer is installed and running. You can also install
the dependencies upfront by running:
```bash
pip install ollama python-docx
```

## Usage
1. Run the application:
```bash
python llm_app.py
```
2. Enter a prompt and select the folder that contains the files you want processed.
3. The model field is pre-filled with the example name/path `gemma-3-12b-it-Q4_K_M.gguf`. You can enter a model **name** that already exists in Ollama or provide a path to a local `.gguf` file. If a path is supplied, the app will automatically run `ollama create` to register the model (it handles both old and new Ollama Python APIs).
4. Pick the desired output format (text or docx) and click **Start** to begin the loop. After each iteration you will be asked whether you want to run again.

Outputs are saved in a new `llm_output` folder within the selected directory.

## Building a Windows executable
If you want to distribute the application as a single `.exe` file you can use
[PyInstaller](https://pyinstaller.org/).

Install the dependencies and PyInstaller:
```bash
pip install -r requirements.txt
pip install pyinstaller
```

Run the provided batch script to create the executable:
```cmd
build_exe.bat
```
The `llm_app.exe` binary will appear in the `dist` folder.
