# 🚀 AutoScript Agent

**An AI-powered Python agent that generates, executes, and captures script outputs from natural language instructions.**

---

## 🧠 Overview

AutoScript Agent is an intelligent system that automates the process of writing and running Python scripts. It uses **Google Gemini** for reasoning and code generation, along with **Pydantic** for validating structured outputs.

The agent understands user instructions, creates scripts, executes them safely, and returns clean, structured results.

---

## ✨ Features

* 🗣️ Accepts natural language instructions
* 🧠 Intelligent reasoning using LLM (Gemini AI)
* 📄 Automatically generates Python scripts
* 💾 Creates and updates files on disk
* ▶️ Executes scripts in a controlled environment
* 📤 Captures stdout, stderr, and exit codes
* ✅ Structured output validation using Pydantic

---

## ⚙️ Workflow

1. User provides a request
2. Agent analyzes the request using LLM
3. Generates a step-by-step plan
4. Creates or updates Python script
5. Executes the script safely
6. Captures output (stdout, stderr, exit code)
7. Returns structured response

---

## 🏗️ Architecture

* **LLM Layer**: Handles reasoning and code generation
* **Validation Layer**: Ensures structured outputs using Pydantic
* **Tool Layer**:

  * File Creator
  * File Editor
  * Script Executor
* **Execution Layer**: Runs scripts safely
* **Output Layer**: Captures and formats results

---

## 📦 Tech Stack

* Python
* Google Gemini AI (LLM)
* Pydantic (Validation)
* Subprocess / OS (Execution & File Handling)

---

## 📁 Project Structure

```
autoscript-agent/
│── agent/
│   ├── planner.py
│   ├── executor.py
│   ├── tools.py
│   └── validator.py
│
│── scripts/
│   └── example.py
│
│── main.py
│── requirements.txt
│── README.md
```

---

## 🚀 Getting Started

### 1. Clone the Repository

```
git clone https://github.com/your-username/autoscript-agent.git
cd autoscript-agent
```

### 2. Install Dependencies

```
pip install -r requirements.txt
```

### 3. Run the Agent

```
python main.py
```

---

## 🧪 Example Usage

**Input:**

```
Create a Python script to print numbers from 1 to 5 and execute it
```

**Output:**

```
1
2
3
4
5
```

---

## 📊 Sample Structured Output

```json
{
  "status": "success",
  "output": "1 2 3 4 5",
  "error": "",
  "exit_code": 0
}
```

---

## 🔒 Safety Considerations

* Controlled execution environment
* Restricted file operations
* Output validation using Pydantic
* Error handling and logging

---

## 📌 Future Improvements

* Add web-based UI
* Support multiple programming languages
* Sandbox execution (Docker)
* Task history and logging dashboard

---

## 📜 License

MIT License

---

