import streamlit as st
import os
from dotenv import load_dotenv
from dependency_injector.wiring import inject, Provide

from aitrading.models import TradingParameters, ExecutionMode
from aitrading.container import Container
from app_state.redis_provider import RedisProvider
from app_state.redis_state import RedisState

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
        },
        "redis": {
            "enabled": True,
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", 6379)),
            "db": int(os.getenv("REDIS_DB", 0)),
            "password": os.getenv("REDIS_PASSWORD", ""),
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

    # Initialize Redis state manager
    redis_provider = RedisProvider()
    if not redis_provider.enabled:
        st.warning("Redis connection not available - parameters will not be persisted")
    state_manager = RedisState(redis_provider)

    # Load last saved state
    saved_state = state_manager.load_state()
    if saved_state:
        logfire.info("Loaded saved interface state", state=saved_state)

    # Model selection
    st.sidebar.header("Model Settings")
    llm_provider = st.sidebar.selectbox(
        "Select AI Model",
        options=AI_PROVIDERS,
        format_func=lambda x: PROVIDER_DISPLAY_NAMES[x],
        index=AI_PROVIDERS.index(saved_state.get("llm_provider", "anthropic")) if saved_state else 0
    )

    # Trading parameters
    symbol = st.text_input("Symbol", value=saved_state.get("symbol", "BTCUSDT") if saved_state else "BTCUSDT")
    if not symbol:
        st.error("Symbol is required")

    col1, col2, col3 = st.columns(3)
    with col1:
        budget = st.number_input(
            "Budget USDT",
            min_value=10,
            value=saved_state.get("budget", 100) if saved_state else 100
        )

    with col2:
        leverage = st.number_input(
            "Leverage",
            min_value=1,
            max_value=100,
            value=saved_state.get("leverage", 1) if saved_state else 1
        )

    with col3:
        timeframe = st.selectbox(
            "Primary Analysis Timeframe",
            options=["15m", "1H", "4H"],
            index=["15m", "1H", "4H"].index(saved_state.get("timeframe", "1H")) if saved_state else 1,
            help="Primary timeframe used for market analysis and pattern recognition"
        )

    if st.button("Create Plan") and symbol:
        # Save current state
        current_state = {
            "llm_provider": llm_provider,
            "symbol": symbol,
            "budget": budget,
            "leverage": leverage,
            "timeframe": timeframe
        }
        saved = state_manager.save_state(current_state)
        if saved:
            logfire.info("Interface state saved", state=current_state)

        with st.spinner("Generating trading plan..."):
            try:
                # Initialize container with selected model
                container = init_container(llm_provider)

                # Create trading parameters
                params = TradingParameters(
                    symbol=symbol,
                    budget=budget,
                    leverage=leverage,
                    stop_loss_config={"timeframe": timeframe},  # Used only for analysis reference
                    execution_mode=ExecutionMode.MANUAL,  # UI is always manual mode
                    analysis_interval=None  # No interval in manual mode
                )

                logfire.info("Generating trading plan with parameters", params=params)
                # Generate plan
                trading_plan = container.trading_planner().create_plan(params)
                logfire.info("Trading plan generated", plan_id=trading_plan.id)

                # Store results
                st.session_state.trading_plan = trading_plan
                logfire.info("Trading plan stored in session",
                            session_keys=list(st.session_state.keys()))

            except Exception as e:
                logfire.exception("Error generating trading plan")
                st.error(f"Error generating trading plan: {str(e)}")
                return

    if st.session_state.trading_plan:
        logfire.info("Rendering trading plan",
                    plan_id=st.session_state.trading_plan.id)
        st.success("Trading plan generated successfully")

        plan = st.session_state.trading_plan
        st.subheader(f"Trading Plan (ID: {plan.id})")

        # Display plan parameters in a more structured way
        with st.expander("Plan Configuration", expanded=False):
            st.write("**Basic Parameters:**")
            st.write(f"- Symbol: {plan.parameters.symbol}")
            st.write(f"- Budget: {plan.parameters.budget} USDT")
            st.write(f"- Leverage: {plan.parameters.leverage}x")
            st.write(f"- Primary Timeframe: {timeframe}")
            st.write(f"- Session ID: {plan.session_id}")
            st.write(f"- Created At: {plan.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            st.write(f"- Execution Mode: {plan.parameters.execution_mode}")
            if plan.parameters.execution_mode == ExecutionMode.SCHEDULER:
                st.write(f"- Analysis Interval: {plan.parameters.analysis_interval} minutes")

        # Display cancellations with improved format
        if plan.cancellations:
            st.subheader("Order Cancellations")
            st.warning(f"{len(plan.cancellations)} orders will be cancelled before executing new plan")
            for cancel in plan.cancellations:
                with st.expander(f"Cancel Order {cancel.order_link_id}", expanded=False):
                    st.write("**Order Details:**")
                    st.write(f"- Order ID: {cancel.id}")
                    st.write(f"- Order Link ID: {cancel.order_link_id}")
                    st.write(f"- Symbol: {cancel.symbol}")
                    st.write(f"- Reason: {cancel.reason}")

        # Display new orders with updated structure
        st.subheader(f"New Orders ({len(plan.orders)})")
        for order in plan.orders:
            with st.expander(
                    f"Order {order.id} - {order.type.upper()} {order.symbol} ({order.execution_type})",
                    expanded=True
            ):
                cols = st.columns([1, 1])

                # Order details
                with cols[0]:
                    st.markdown("##### Order Details")
                    st.write(f"**Direction:** {order.type.upper()}")
                    st.write(f"**Entry Type:** {order.order.type.upper()}")
                    if order.order.type == 'limit':
                        st.write(f"**Entry Price:** {order.order.entry.price}")
                    st.write(f"**Budget:** {order.order.entry.budget} USDT")
                    st.write(f"**Leverage:** {order.order.entry.leverage}x")
                    st.write(f"**Execution Type:** {order.execution_type}")
                    st.write(f"**Risk Level:** {order.risk_level}")
                    if order.current_price:
                        st.write(f"**Current Price:** {order.current_price}")

                # Strategic context
                with cols[1]:
                    st.markdown("##### Strategic Context")
                    st.write(f"**Market Bias:** {order.strategic_context.market_bias}")

                    st.write("**Key Levels:**")
                    for level in order.strategic_context.key_levels:
                        st.write(f"- {level}")

                    st.write("**Catalysts:**")
                    for catalyst in order.strategic_context.catalysts:
                        st.write(f"- {catalyst}")

                # Expanded rationale in a new section
                st.markdown("##### Setup Analysis")
                st.write(f"**Setup Rationale:**")
                st.write(order.strategic_context.setup_rationale)

                st.write("**Invalidation Conditions:**")
                for condition in order.strategic_context.invalidation_conditions:
                    st.write(f"- {condition}")

        # Market Analysis Section
        st.divider()
        st.markdown("### Market Analysis")
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
                                if cancel_result.get("status") == "success":
                                    st.success(
                                        f"Successfully cancelled order {cancel_result['order_link_id']}"
                                    )
                                else:
                                    st.error(
                                        f"Failed to cancel order {cancel_result['order_link_id']}: "
                                        f"{cancel_result.get('error', 'Unknown error')}"
                                    )

                    # Show new order results with improved details
                    with st.expander("Order Execution Results", expanded=True):
                        st.write(f"**{len(result['orders'])} orders placed**")
                        for order_result in result["orders"]:
                            if "error" in order_result:
                                st.error(
                                    f"Failed to place order {order_result['order_link_id']}: "
                                    f"{order_result['error']}"
                                )
                            else:
                                st.success(
                                    f"Successfully placed order {order_result['order_link_id']}"
                                )
                                if "result" in order_result:
                                    st.write("Order Details:")
                                    st.json(order_result["result"])

                except Exception as e:
                    st.error(f"Error executing trading plan: {str(e)}")


if __name__ == "__main__":
    render_strategy_ui()