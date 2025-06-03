# Tiny Planet LLM App

This repository includes a small Tkinter-based application to run a local language model on Windows. The GUI lets you enter a prompt, choose a folder to process, select the model file and pick an output format.

## Requirements
- Python 3.10 or newer
- `python-docx` if you want to save output as `.docx`

The application will attempt to install `llama-cpp-python` automatically the
first time it is launched. If you prefer to install dependencies manually run:
```bash
pip install llama-cpp-python python-docx
```

## Usage
1. Run the application:
```bash
python llm_app.py
```
2. Enter a prompt and select the folder that contains the files you want processed.
3. The model path field is pre-filled with the example path to `gemma-3-12b-it-Q4_K_M.gguf` on Windows. Change it if your model is located elsewhere.
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
