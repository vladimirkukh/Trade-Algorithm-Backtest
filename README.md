# Algo Backtester

A lightweight algorithmic trading backtester built with Python and Streamlit. This application allows users to test technical trading strategies on historical market data, adjust parameters in real-time, and analyze performance through interactive charts and detailed trade logs.

## Features

- **Interactive Strategy Controls:** Easily adjust parameters like the ATR Period and Sensitivity using sidebar sliders.
- **Dynamic Visualizations:** View a responsive equity curve powered by Plotly, with the option to toggle a Buy & Hold benchmark.
- **Performance Metrics:** Instantly track key metrics including Total Return, Total Trades, and Win Rate.
- **Comprehensive Trade Log:** Inspect individual trades with color-coded returns, entry/exit prices, and dates.

## Tech Stack

- **Frontend & UI:** [Streamlit](https://streamlit.io/)
- **Data Manipulation:** [Pandas](https://pandas.pydata.org/)
- **Data Visualization:** [Plotly](https://plotly.com/)

---
## Web Address
http://145.241.206.63:8502
## How to Run Locally

If you want to run this project on your local machine, follow these steps:

### Clone the repository

```bash
git clone https://github.com/vladimirkukh/Trade-Algorithm-Backtest.git
cd [YOUR REPOSITORY]
```

### Create a virtual environment (recommended)

macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows

```bash
python -m venv venv
venv\Scripts\activate
```
### Install the required packages

```bash
pip install -r requirements.txt
```

### Run the application

```bash
streamlit run app.py
```

The application will open automatically in your web browser.

---
