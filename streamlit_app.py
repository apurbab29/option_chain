import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Cache expiration dates to prevent redundant API calls
@st.cache_data
def get_all_expiration_dates(ticker_symbol):
    """Fetch all expiration dates for the given ticker."""
    ticker = yf.Ticker(ticker_symbol)
    try:
        return ticker.options
    except:
        return []

@st.cache_data
def get_options_chain(ticker_symbol, expiration):
    """Fetch options data for a given expiration date."""
    ticker = yf.Ticker(ticker_symbol)
    try:
        options_chain = ticker.option_chain(expiration)
        calls_df, puts_df = options_chain.calls.copy(), options_chain.puts.copy()
        calls_df["option_type"], puts_df["option_type"] = "Call", "Put"
        df = pd.concat([calls_df, puts_df], ignore_index=True)
        df["expiration_date"] = expiration
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def get_valid_expirations(ticker_symbol):
    """Return only expiration dates where at least one option has openInterest > 0."""
    all_expirations = get_all_expiration_dates(ticker_symbol)
    valid_expirations = []

    for expiry in all_expirations:
        df = get_options_chain(ticker_symbol, expiry)
        if not df.empty and df["openInterest"].sum() > 0:
            valid_expirations.append(expiry)

    return valid_expirations

def adjust_xticks(ax, df):
    """Automatically adjusts x-axis scale based on unique strike prices."""
    num_strikes = len(df["strike"].unique())
    if num_strikes > 20:
        ax.set_xticks(ax.get_xticks()[::num_strikes // 20])
    ax.set_xticklabels(ax.get_xticklabels(), rotation=90)

def plot_change_in_open_interest(df):
    """Plots Change in Open Interest (ΔOI) against Strike Price."""
    if "prev_openInterest" not in df.columns:
        df["prev_openInterest"] = df.groupby("strike")["openInterest"].shift(1, fill_value=0)
    
    df["change_in_OI"] = df["openInterest"] - df["prev_openInterest"]
    df_filtered = df[df["change_in_OI"] != 0]  # Filter zero changes
    
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(
        x="strike", 
        y="change_in_OI", 
        hue="option_type", 
        data=df_filtered, 
        ax=ax,
        palette={"Call": "green", "Put": "red"}  # Calls in Green, Puts in Red
    )
    
    ax.set_xticklabels(ax.get_xticklabels(), rotation=90)
    ax.set_xlabel("Strike Price")
    ax.set_ylabel("Change in Open Interest (ΔOI)")
    ax.set_title("Change in Open Interest vs. Strike Price")
    
    return fig

def plot_volume(df):
    filtered_vol_data = df[df["volume"] > 0]
    fig, ax = plt.subplots(figsize=(14, 7))
    sns.barplot(x="strike", y="volume", hue="option_type", data=filtered_vol_data, ax=ax, palette={"Call": "green", "Put": "red"})
    adjust_xticks(ax, filtered_vol_data)
    ax.set_xlabel("Strike Price")
    ax.set_ylabel("Volume")
    ax.set_title("Volume vs. Strike Price (Filtered for Volume > 0)")
    return fig

def plot_open_interest_sorted(df):
    df_sorted = df[df["openInterest"] > 0].sort_values(by=["expiration_date", "strike"], ascending=[False, True])
    fig, ax = plt.subplots(figsize=(14, 7))
    sns.barplot(x="strike", y="openInterest", hue="option_type", data=df_sorted, ax=ax, palette={"Call": "green", "Put": "red"})
    adjust_xticks(ax, df_sorted)
    ax.set_xlabel("Strike Price (Ordered by Days to Expiry Descending)")
    ax.set_ylabel("Open Interest")
    ax.set_title("Open Interest vs. Strike Price (Grouped by Call/Put, Ordered by Days to Expiry Descending)")
    return fig

# Streamlit UI
st.title("Optimized Options Chain Dashboard")

ticker_symbol = st.text_input("Enter a US Stock Symbol (e.g., AAPL, TSLA, MSFT):").upper()

if ticker_symbol:
    valid_dates = get_valid_expirations(ticker_symbol)  # Fetch only valid expiration dates

    if valid_dates:
        selected_expiry = st.selectbox("Select an Expiration Date:", valid_dates)

        if "options_data" not in st.session_state or st.session_state.get("selected_expiry") != selected_expiry:
            st.session_state["options_data"] = None
            st.session_state["data_fetched"] = False

        if st.button("Fetch Options Data"):
            st.session_state["options_data"] = get_options_chain(ticker_symbol, selected_expiry)
            st.session_state["data_fetched"] = True
            st.session_state["selected_expiry"] = selected_expiry

        if st.session_state.get("data_fetched", False):
            options_data = st.session_state["options_data"]

            if not options_data.empty:
                st.success("Data fetched successfully!")
                st.download_button("Download CSV", options_data.to_csv(index=False), f"{ticker_symbol}_options.csv", "text/csv")

                plot_choice = st.selectbox("Choose a bar plot to display:",
                                           ["Change in Open Interest vs Strike Price",
                                            "Volume vs Strike Price",
                                            "Open Interest Sorted by Expiry"], key="plot_selector")

                plot_container = st.empty()
                if plot_choice == "Change in Open Interest vs Strike Price":
                    plot_container.pyplot(plot_change_in_open_interest(options_data))
                elif plot_choice == "Volume vs Strike Price":
                    plot_container.pyplot(plot_volume(options_data))
                elif plot_choice == "Open Interest Sorted by Expiry":
                    plot_container.pyplot(plot_open_interest_sorted(options_data))
            else:
                st.error("No options data found.")
    else:
        st.warning("No valid expiration dates found.")
