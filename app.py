import streamlit as st
from groq import Groq
from datetime import datetime
import json
import os
import pandas as pd

# पेज सेटअप - कंपनी का नाम RV किया
st.set_page_config(page_title="RV - Financial AI", page_icon="💼", layout="wide")

API_KEY = st.secrets["GROQ_API_KEY"]
EXCEL_FILE = "financial_records.xlsx"

# एक्सेल फाइल में रिकॉर्ड दर्ज करने का फंक्शन
def record_transaction(date, transaction_type, category, amount, description):
    new_data = {
        "Date": [date],
        "Type": [transaction_type],
        "Category": [category],
        "Amount": [float(amount)],
        "Description": [description]
    }
    df_new = pd.DataFrame(new_data)
    
    if os.path.exists(EXCEL_FILE):
        df_old = pd.read_excel(EXCEL_FILE)
        df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new
        
    df_final.to_excel(EXCEL_FILE, index=False)
    return f"सफलतापूर्वक Excel में रिकॉर्ड कर लिया गया है: {category} के लिए ₹{amount} ({transaction_type})"

# Groq क्लाइंट सेटअप
client = Groq(api_key=API_KEY)

# लेआउट डिजाइन - हेडिंग में RV किया
st.title("💼 RV - AI Financial Advisor")
st.markdown("---")

# दो भाग बनाना: बायीं तरफ चैट और दायीं तरफ एक्सेल डेटा का व्यू
col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("📊 लाइव बहीखाता (Excel Live View)")
    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
        # कुल कमाई और खर्च दिखाना
        income = df[df["Type"] == "Income"]["Amount"].sum()
        expense = df[df["Type"] == "Expense"]["Amount"].sum()
        balance = income - expense
        
        st.metric(label="कुल कमाई (Total Income)", value=f"₹{income:,.2f}")
        st.metric(label="कुल खर्च (Total Expense)", value=f"₹{expense:,.2f}", delta=f"-₹{expense:,.2f}", delta_color="inverse")
        st.metric(label="नेट बैलेंस (Net Balance)", value=f"₹{balance:,.2f}")
        
        st.dataframe(df.tail(10), use_container_width=True)
    else:
        st.info("अभी तक कोई लेनदेन रिकॉर्ड नहीं हुआ है।")

with col1:
    st.subheader("💬 अपने एडवाइजर से बात करें")
    
    # चैट हिस्ट्री को बनाए रखना
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # यूज़र इनपुट
    if user_input := st.chat_input("यहाँ अपना सवाल या खर्च लिखें..."):
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # लाइव तारीख निकालना
        current_date = datetime.now().strftime("%Y-%m-%d")

        # टूल्स डेफिनेशन
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "record_transaction",
                    "description": "बिजनेस के खर्च (Expense) या कमाई (Income) को Excel शीट में दर्ज करने के लिए।",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "transaction_type": {"type": "string", "enum": ["Income", "Expense"]},
                            "category": {"type": "string"},
                            "amount": {"type": "number"},
                            "description": {"type": "string"}
                        },
                        "required": ["transaction_type", "category", "amount", "description"]
                    }
                }
            }
        ]

        # सिस्टम इंस्ट्रक्शन में कंपनी का नाम RV किया
        system_instruction = (
            f"You are the expert Financial Advisor for RV. Today's date is {current_date}. "
            f"If the user tells you about any income or expense, you MUST use the 'record_transaction' tool to save it. "
            f"Always reply in friendly Hindi or Hinglish."
        )

        # AI रिपॉन्स जेनरेशन
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_input}
            ],
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        ai_reply = ""

        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name == "record_transaction":
                    result = record_transaction(
                        date=current_date,
                        transaction_type=function_args.get("transaction_type"),
                        category=function_args.get("category"),
                        amount=function_args.get("amount"),
                        description=function_args.get("description")
                    )
                    
                    final_response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": user_input},
                            response_message,
                            {"role": "tool", "tool_call_id": tool_call.id, "name": function_name, "content": result}
                        ]
                    )
                    ai_reply = final_response.choices[0].message.content
                    st.rerun()  # स्क्रीन को रिफ्रेश करना ताकि नया एक्सेल डेटा दिख सके
        else:
            ai_reply = response_message.content

        with st.chat_message("assistant"):
            st.markdown(ai_reply)
        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
