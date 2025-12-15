# 🧬 Micro-Quant | Tactical Engine

**Micro-Quant** is a specialized swing trading dashboard that blends **Technical Analysis** (Micro) with **Trend Quality Filtering** (Macro). 

It utilizes J. Welles Wilder’s **ADX** (Trend Strength) and **ATR** (Volatility) to filter out "choppy" price action, preventing false buy signals in sideways markets.

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.11.4-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ⚡ Key Features

* **Trend Quality Filter:** Automatically rejects setups if **ADX < 20** (The "Chop Zone").
* **Volatility-Based Risk:** Dynamically calculates Stop Loss levels using `2 * ATR`.
* **Solvency Check:** The "Banker" logic prevents trades that violate your Risk % or exceed your Account Size.
* **Paper Trading Ready:** Built-in support for **Alpaca** API and manual workflows for **Moomoo/Webull**.
* **Data Persistence:** Uses a lightweight SQLite database (`scanner.db`) to remember your settings between sessions.

---

## 🛠️ Installation & Setup

We use **Micromamba** for a fast, robust Python environment. This is highly recommended for **Apple Silicon (M1/M2/M3)** users to avoid Python version conflicts.

### 1. Prerequisites
If you don't have Micromamba installed:

* **🪟 Windows 11 (PowerShell)**
    ```powershell
    Invoke-Expression ((Invoke-WebRequest -Uri [https://micro.mamba.pm/install.ps1](https://micro.mamba.pm/install.ps1) -UseBasicParsing).Content)
    ```

* **🍎 macOS (Apple Silicon / Intel)**
    ```bash
    "${SHELL}" <(curl -L micro.mamba.pm/install.sh)
    ```
    *(Restart your terminal after installation)*

### 2. Create the Environment
Clone this repo, then create the isolated environment using the provided config. This automatically handles the specific `pandas-ta` fix required for Python 3.11.

```bash
# 1. Create environment from file
micromamba create -f environment.yml

# 2. Activate the environment
micromamba activate micro-quant