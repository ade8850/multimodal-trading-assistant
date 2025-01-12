# SuperBotAI Trading System

⚠️ **EXPERIMENTAL PROJECT - USE AT YOUR OWN RISK** ⚠️

SuperBotAI is an experimental AI-powered trading system that leverages multimodal AI capabilities to analyze market charts and create trading strategies. This project demonstrates the potential of AI in automated trading while exploring new approaches to market analysis.

## ⚠️ Important Notice

This is an **experimental project** and should not be used for actual trading without thorough testing and understanding of the risks involved. The authors are not responsible for any financial losses incurred through the use of this system.

## 🔍 Key Features

The system utilizes multimodal AI models to analyze market charts and technical patterns, integrating visual analysis capabilities with automated trading execution. It supports multiple AI providers and includes both a web-based interface for creating individual trading strategies and a scheduler for continuous automated execution.

## 🛠 Technology Stack

- **Backend**: Python with dependency injection architecture
- **AI Models**: 
  - Claude (Anthropic)
  - Gemini Pro Vision (Google)
  - GPT-4 Vision (OpenAI)
- **Trading Interface**: Bybit API (pybit)
- **Web Interface**: Streamlit

## 🚀 Getting Started

### Prerequisites

- Python 3.12 (not tested with other versions)
- Redis server (required for Streamlit interface only)
- Docker (optional)
- API keys for:
  - Bybit
  - At least one AI provider (Anthropic/Google/OpenAI)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/ade8850/superbot-ai-app.git
cd superbot-ai-app
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
cp scheduler_config.example.yaml config.yaml
# Edit config.yaml with your trading parameters
```

5. Run the application:
```bash
# Web interface
streamlit run app.py

# Scheduler
python scheduler.py
```

### Docker Deployment

```bash
# Build and run the web interface
docker build -t superbotai .
docker run -p 8501:8501 superbotai

# Build and run the scheduler
docker build -f scheduler.Dockerfile -t superbotai-scheduler .
docker run superbotai-scheduler
```

## 📊 How It Works

1. **Market Analysis**:
   - The system uses multimodal AI capabilities to analyze market charts
   - Visual patterns and market context are evaluated using natural language processing

2. **Strategy Generation**:
   - AI models process the visual analysis and market context
   - Trading strategies are generated based on identified patterns

3. **Order Execution**:
   - Strategies are converted into concrete trading orders
   - Orders are executed through the Bybit API

## ⚙️ Configuration

The system can be configured through:
- Environment variables (.env file)
- Web interface settings
- YAML configuration files for the scheduler (config.yaml)

See `scheduler_config.example.yaml` for scheduler configuration options.

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