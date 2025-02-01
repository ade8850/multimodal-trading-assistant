# Multi modal trading assistant

⚠️ **EXPERIMENTAL PROJECT - USE AT YOUR OWN RISK** ⚠️

This is an experimental AI-powered trading system that combines multimodal artificial intelligence with automated risk management. The system analyzes market charts using advanced visual AI capabilities while implementing systematic risk controls through dynamic stop loss management.

## ⚠️ Important Notice

This is an **experimental project** and should not be used for actual trading without thorough testing and understanding of the risks involved. The authors are not responsible for any financial losses incurred through the use of this system.

## 🔍 Key Features

The system combines AI-driven analysis with automated risk management to create a comprehensive trading solution. At its core, the system processes market data in two distinct ways: visual analysis for trade opportunities and systematic risk management for position protection.

The multimodal AI component analyzes market charts and technical patterns to identify potential trading opportunities. This analysis considers multiple timeframes and various technical indicators to form a complete market view.

The automated risk management system implements a dynamic stop loss strategy based on market volatility and position performance. This system adapts protection levels as positions evolve, providing tighter risk control in volatile conditions while allowing profitable trades room to develop.

Additional features include:
- Integration with multiple AI providers (Anthropic Claude, Google Gemini, OpenAI GPT-4)
- Support for multiple trading pairs and timeframes
- Comprehensive logging and monitoring through Logfire
- Web-based interface for strategy creation and monitoring
- Automated trading scheduler for continuous operation

## 📊 Risk Management

The system implements an advanced automated risk management strategy that adapts to market conditions and position performance:

Position Protection:
- Stop losses are calculated using Average True Range (ATR) to account for market volatility
- Protection levels automatically adjust based on position performance
- Two-tiered system provides different ATR multipliers based on whether the position is in profit or not

Risk Bands:
1. Initial Protection Band: Conservative stop loss placement for new positions (not in profit)
2. In Profit Band: Adjusted protection when the stop loss is above the entry price (for long positions) or below the entry price (for short positions)

All risk parameters are fully configurable through the web interface or configuration files, allowing for customization while maintaining systematic risk control.

## 🛠 Technology Stack

The system is built using modern Python technologies:

Core Components:
- Python 3.12
- Pydantic for data validation
- Streamlit for web interface
- Plotly for technical analysis charts

Integration Points:
- Bybit API through pybit
- Multiple AI providers supported (Anthropic, Google, OpenAI)
- Primary testing and optimization conducted with **Anthropic's Claude**
- Logfire for structured logging

## 🚀 Getting Started

### Prerequisites

- Python 3.12 (not tested with other versions)
- Docker (optional)
- API keys for:
  - Bybit
  - At least one AI provider (Anthropic/Google/OpenAI)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/ade8850/multimodal-trading-assistant.git
cd multimodal-trading-assistant
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

4. Set up scheduler configuration:
```bash
cp scheduler_config.example.yaml scheduler_config.yaml
# Edit scheduler_config.yaml with your trading parameters
```

5. Run the application:
```bash
# Web interface
streamlit run app.py

# Scheduler
./run_scheduler.sh
```

## 📊 How It Works

The system operates through three main phases:

1. Technical Analysis
   - AI models analyze market charts across multiple timeframes
   - Technical patterns and market context are evaluated
   - Key support and resistance levels are identified

2. Decision Making
   - Entry opportunities are identified based on technical analysis
   - Position sizing considers current market volatility
   - Stop loss levels are calculated using ATR-based algorithm

3. Risk Management
   - Positions are continuously monitored
   - Stop losses adjust automatically based on market conditions
   - Protection levels adapt to position performance

## ⚙️ Configuration

The system can be configured through:
- Environment variables (.env file)
- YAML configuration files (scheduler_config.yaml)
Both trading parameters and risk management settings are fully customizable through these files.

## 🤝 Contributing

While this project is maintained in the author's spare time, contributions are very welcome! Feel free to submit both ideas and code through Pull Requests or Issues. The author will do their best to review and incorporate valuable contributions despite time limitations.

For major changes, please open an issue first to discuss what you would like to change.

## 📜 License

This software is released under a dual license:

### Personal Use License
- Free to use for personal, non-commercial purposes
- Modifications and redistribution allowed for personal use
- Must maintain attribution and all license notices

### Commercial/Institutional Use
- Any use by companies, institutions, or organizations requires explicit written permission
- This includes but is not limited to:
  - Commercial deployments
  - Use in corporate environments
  - Educational institutions
  - Government organizations
  - Non-profit organizations using it as part of their operations

For commercial/institutional licensing inquiries, please open an issue or use GitHub's discussion features.

See the [LICENSE](LICENSE) file for the complete license terms.

## ⚠️ Risk Disclaimer

This software is for educational and experimental purposes only. Cryptocurrency trading involves substantial risk and is not suitable for every investor. The high degree of leverage can work against you as well as for you. Before deciding to trade cryptocurrency you should carefully consider your investment objectives, level of experience, and risk appetite.

The possibility exists that you could sustain a loss of some or all of your initial investment and therefore you should not invest money that you cannot afford to lose. You should be aware of all the risks associated with cryptocurrency trading, and seek advice from an independent financial advisor if you have any doubts.

## 📧 Contact

- Create an Issue for bug reports or feature requests
- Submit a Pull Request to contribute