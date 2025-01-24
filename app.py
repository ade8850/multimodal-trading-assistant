# aitrading/streamlit/app.py

import streamlit as st
import os
import redis
from dotenv import load_dotenv
from dependency_injector.wiring import inject, Provide

from aitrading.models import TradingParameters
from aitrading.container import Container

import logfire

# Load environment variables
load_dotenv()

logfire.configure(
    environment="local",
    send_to_logfire="if-token-present",
    scrubbing=False,
)

# Provider display mapping
PROVIDER_DISPLAY_NAMES = {
    "anthropic": "Anthropic",
    "gemini": "Gemini",
    "openai": "OpenAI"
}

# Available AI providers
AI_PROVIDERS = list(PROVIDER_DISPLAY_NAMES.keys())

# Redis configuration
REDIS_KEY_PLAN = "default_plan_instructions"
DEFAULT_PLAN = """Find the most appropriate trading opportunities based on market conditions.
If the current market condition is too uncertain, place orders in safe areas while waiting for a favorable trend.
Maximize the probability of profit rather than the profit itself."""


def get_redis_client():
    """Initialize Redis client with configuration from environment."""
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        password=os.getenv("REDIS_PASSWORD", ""),
        decode_responses=True
    )


def get_plan_instructions():
    """Retrieve plan instructions from Redis or return default."""
    try:
        redis_client = get_redis_client()
        stored_instructions = redis_client.get(REDIS_KEY_PLAN)
        return stored_instructions if stored_instructions else DEFAULT_PLAN
    except Exception as e:
        st.warning(f"Could not retrieve stored instructions: {str(e)}")
        return DEFAULT_PLAN


def save_plan_instructions(instructions):
    """Save plan instructions to Redis."""
    try:
        redis_client = get_redis_client()
        redis_client.set(REDIS_KEY_PLAN, instructions)
    except Exception as e:
        st.warning(f"Could not save instructions: {str(e)}")


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

    # Plan Instructions
    st.header("Plan Instructions")
    plan_instructions = st.text_area(
        "Trading Plan Instructions",
        help="Enter specific instructions or constraints for the trading plan",
        value=get_plan_instructions(),
        height=150,
        key="ui:last_plan_instructions"
    )

    # Save instructions if changed
    if "last_instructions" not in st.session_state:
        st.session_state.last_instructions = plan_instructions

    if st.session_state.last_instructions != plan_instructions:
        save_plan_instructions(plan_instructions)
        st.session_state.last_instructions = plan_instructions

    if st.button("Create Plan") and symbol:
        with st.spinner("Generating trading plan..."):
            try:
                # Initialize container with selected model
                container = init_container(llm_provider)

                # Create trading parameters
                params = TradingParameters(
                    symbol=symbol,
                    budget=budget,
                    leverage=leverage,
                    strategy_instructions=plan_instructions
                )

                # Generate plan
                trading_plan = container.trading_planner().create_trading_plan(params)

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

        # Display position updates if any
        if plan.position_updates:
            st.subheader("Position Updates")
            st.info(f"{len(plan.position_updates)} positions will have TP/SL levels updated")
            for update in plan.position_updates:
                with st.expander(f"Update Position {update.symbol}", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        if update.take_profit:
                            st.write(f"**New Take Profit:** {update.take_profit}")
                    with col2:
                        if update.stop_loss:
                            st.write(f"**New Stop Loss:** {update.stop_loss}")
                    st.write(f"**Reason:** {update.reason}")

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

                    # Show position update results if any
                    if result.get("position_updates"):
                        with st.expander("Position Update Results", expanded=True):
                            st.write(f"**{len(result['position_updates'])} position updates executed**")
                            for update_result in result["position_updates"]:
                                if update_result["success"]:
                                    st.success(f"Position {update_result['symbol']} updated successfully")
                                else:
                                    st.error(f"Position {update_result['symbol']}: {update_result['error']}")

                    # Show new order results
                    with st.expander("Order Execution Results", expanded=True):
                        st.write(f"**{len(result['orders'])} orders placed**")
                        for order_result in result["orders"]:
                            if "error" in order_result:
                                st.error(f"Order {order_result['order_link_id']}: {order_result['error']}")
                            else:
                                st.success(f"Order {order_result['order_link_id']} placed successfully")

                except Exception as e:
                    st.error(f"Error executing trading plan: {str(e)}")


if __name__ == "__main__":
    render_strategy_ui()