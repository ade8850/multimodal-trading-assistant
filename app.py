import streamlit as st
import os
from dotenv import load_dotenv
from dependency_injector.wiring import inject, Provide

from aitrading.models import TradingParameters
from aitrading.container import Container
from aitrading.tools.stop_loss import StopLossConfig

import logfire

# Load environment variables
load_dotenv()

logfire.configure(
    send_to_logfire="if-token-present",
    scrubbing=False,
    service_name="streamlit-app"
)

# Provider display mapping
PROVIDER_DISPLAY_NAMES = {
    "anthropic": "Anthropic",
    "gemini": "Gemini",
    "openai": "OpenAI"
}

# Available AI providers
AI_PROVIDERS = list(PROVIDER_DISPLAY_NAMES.keys())

def init_container(llm_provider: str) -> Container:
    """Initialize the dependency injection container."""
    container = Container()

    # Configure container
    container.config.update({
        "bybit": {
            "api_key": os.getenv("BYBIT_API_KEY"),
            "api_secret": os.getenv("BYBIT_API_SECRET"),
            "testnet": os.getenv("BYBIT_TESTNET", "False").lower() == "true"
        },
        "llm": {
            "provider": llm_provider,
            "api_key": (os.getenv("ANTHROPIC_API_KEY") if llm_provider == "anthropic"
                       else os.getenv("GEMINI_API_KEY") if llm_provider == "gemini"
                       else os.getenv("OPENAI_API_KEY"))
        }
    })

    logfire.info("Container initialized")
    container.wire(modules=["__main__"])
    return container

@inject
def render_strategy_ui(container: Container = Provide[Container]):
    """Render the main Streamlit UI."""
    st.title("AI Trading Planner")

    if "trading_plan" not in st.session_state:
        st.session_state.trading_plan = None

    # Model selection
    st.sidebar.header("Model Settings")
    llm_provider = st.sidebar.selectbox(
        "Select AI Model",
        options=AI_PROVIDERS,
        format_func=lambda x: PROVIDER_DISPLAY_NAMES[x]
    )

    # Trading parameters
    symbol = st.text_input("Symbol", value="BTCUSDT")
    if not symbol:
        st.error("Symbol is required")

    col1, col2 = st.columns(2)
    with col1:
        budget = st.number_input("Budget USDT", min_value=10, value=100)

    with col2:
        leverage = st.number_input("Leverage", min_value=1, max_value=100, value=1)

    # Stop Loss Configuration
    st.header("Stop Loss Management")
    stop_loss_enabled = st.checkbox("Enable Automatic Stop Loss Management", value=True)

    if stop_loss_enabled:
        sl_col1, sl_col2 = st.columns(2)
        with sl_col1:
            timeframe = st.selectbox(
                "ATR Timeframe",
                options=["15m", "1H", "4H"],
                index=1,
                help="Timeframe used for ATR calculation"
            )
            initial_multiplier = st.number_input(
                "Initial ATR Multiplier",
                min_value=0.5,
                max_value=5.0,
                value=1.5,
                step=0.1,
                help="ATR multiplier for positions not in profit"
            )

        with sl_col2:
            in_profit_multiplier = st.number_input(
                "In Profit ATR Multiplier",
                min_value=0.5,
                max_value=5.0,
                value=2.0,
                step=0.1,
                help="ATR multiplier for positions in profit"
            )

    if st.button("Create Plan") and symbol:
        with st.spinner("Generating trading plan..."):
            try:
                # Initialize container with selected model
                container = init_container(llm_provider)

                # Prepare stop loss configuration if enabled
                stop_loss_config = None
                if stop_loss_enabled:
                    stop_loss_config = {
                        "timeframe": timeframe,
                        "initial_multiplier": initial_multiplier,
                        "in_profit_multiplier": in_profit_multiplier
                    }

                # Create trading parameters
                params = TradingParameters(
                    symbol=symbol,
                    budget=budget,
                    leverage=leverage,
                    stop_loss_config=stop_loss_config
                )

                # Generate plan
                trading_plan = container.trading_planner().create_plan(params)

                # Store results
                st.session_state.trading_plan = trading_plan

            except Exception as e:
                st.error(f"Error generating trading plan: {str(e)}")
                return

    if st.session_state.trading_plan:
        st.success("Trading plan generated successfully")

        plan = st.session_state.trading_plan
        st.subheader(f"Trading Plan (ID: {plan.id})")

        # Display plan parameters
        with st.expander("Plan Parameters", expanded=False):
            st.json(plan.parameters.model_dump())

        # Display cancellations if any
        if plan.cancellations:
            st.subheader("Order Cancellations")
            st.warning(f"{len(plan.cancellations)} orders will be cancelled before executing new plan")
            for cancel in plan.cancellations:
                with st.expander(f"Cancel Order {cancel.order_link_id}", expanded=False):
                    st.write(f"**Reason:** {cancel.reason}")
                    st.json(cancel.model_dump(exclude={'reason'}))

        # Display new orders
        st.subheader(f"New Orders ({len(plan.orders)})")
        for order in plan.orders:
            with st.expander(f"Order {order.id} - {order.type.upper()} {order.symbol}", expanded=True):
                # Order Info
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Type:** {order.type.upper()}")
                    st.write(
                        f"**Entry Price:** {'Market' if order.order.type == 'market' else order.order.entry.price}")
                    st.write(f"**Budget:** {order.order.entry.budget} USDT")
                    st.write(f"**Leverage:** {order.order.entry.leverage}x")
                with col2:
                    st.write(f"**Take Profit:** {order.order.exit.take_profit.price}")
                    st.write(f"**Stop Loss:** {order.order.exit.stop_loss.price}")

                # Rationale
                st.markdown("---")
                st.markdown("#### Rationale")
                st.write(f"**Trend:** {order.rationale.trend}")
                st.write("**Key Levels:**")
                for level in order.rationale.key_levels:
                    st.write(f"- {level}")
                st.write("**Catalysts:**")
                for catalyst in order.rationale.catalysts:
                    st.write(f"- {catalyst}")

        st.divider()
        st.markdown("### Analysis")
        st.markdown(plan.analysis)

        # Execute Plan Button
        if st.button("Execute Plan"):
            with st.spinner("Executing trading plan..."):
                try:
                    container = init_container(llm_provider)
                    result = container.trading_planner().execute_plan(plan)

                    # Show execution results
                    st.success("Trading plan executed")

                    # Show cancellation results if any
                    if result.get("cancellations"):
                        with st.expander("Cancellation Results", expanded=False):
                            st.write(f"**{len(result['cancellations'])} orders cancelled**")
                            for cancel_result in result["cancellations"]:
                                st.write(f"Order {cancel_result['order_link_id']}: {cancel_result['status']}")
                                if cancel_result.get("error"):
                                    st.error(cancel_result["error"])

                    # Show new order results
                    with st.expander("Order Execution Results", expanded=True):
                        st.write(f"**{len(result['orders'])} orders placed**")
                        for order_result in result["orders"]:
                            if "error" in order_result:
                                st.error(f"Order {order_result['order_link_id']}: {order_result['error']}")
                            else:
                                st.success(f"Order {order_result['order_link_id']} placed successfully")

                    # Show stop loss update results if any
                    if "stop_loss_updates" in result:
                        with st.expander("Stop Loss Updates", expanded=True):
                            updates = result["stop_loss_updates"]
                            st.write(f"**{len(updates.get('updates', []))} stop loss updates executed**")
                            for update in updates.get("updates", []):
                                st.success(f"Position {update['position_id']} stop loss updated")
                                st.write(f"New stop loss: {update['update']['new_stop_loss']}")
                                st.write(f"Reason: {update['update']['reason']}")

                            if updates.get("errors"):
                                for error in updates["errors"]:
                                    st.error(f"Error updating position {error['position_id']}: {error['error']}")

                except Exception as e:
                    st.error(f"Error executing trading plan: {str(e)}")

if __name__ == "__main__":
    render_strategy_ui()