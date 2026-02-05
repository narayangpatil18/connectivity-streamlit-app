import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# ======================================================
# PAGE CONFIG
# ======================================================
st.set_page_config(
    page_title="Connectivity Processor",
    page_icon="📊",
    layout="wide"
)

# ======================================================
# CUSTOM CSS (Buttons, logo sharpness, clean UI)
# ======================================================
st.markdown(
    """
    <style>
    footer {visibility: hidden;}

    /* Sharper images */
    img {
        image-rendering: -webkit-optimize-contrast;
        image-rendering: crisp-edges;
    }

    /* Red Run button */
    div.stButton > button:first-child {
        background-color: #d71920;
        color: white;
        font-weight: bold;
        border-radius: 10px;
        height: 3.2em;
        width: 100%;
        border: none;
    }

    /* Green Download button */
    div[data-testid="stDownloadButton"] > button {
        background-color: #2e7d32;
        color: white;
        font-weight: bold;
        border-radius: 10px;
        height: 3.2em;
        width: 100%;
        border: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ======================================================
# HEADER WITH LOGO
# ======================================================
col1, col2 = st.columns([6, 2])

with col1:
    st.title("Connectivity Processing Tool")

with col2:
    st.image("molbio.png", width=180)   # ⬅️ slightly larger logo

# Developer credit (bigger & visible)
st.markdown(
    """
    <p style="text-align:center; font-size:20px; margin-top:-10px;">
        Developed by <b>Narayan G Patil</b>
    </p>
    """,
    unsafe_allow_html=True
)

st.markdown("---")

# ======================================================
# FILE UPLOAD SECTION
# ======================================================
st.subheader("Upload Input Files")

csv_files = st.file_uploader(
    "📂 Upload exactly 2 CSV files",
    type=["csv"],
    accept_multiple_files=True
)

master_file = st.file_uploader(
    "📄 Upload Master Excel File",
    type=["xlsx"]
)

run_button = st.button("▶ Run Processing")

# ======================================================
# PROCESSING LOGIC
# ======================================================
if run_button:

    # ------------------ Validation ------------------
    if csv_files is None or len(csv_files) != 2:
        st.error("❌ Please upload exactly 2 CSV files.")
        st.stop()

    if master_file is None:
        st.error("❌ Please upload the Master Excel file.")
        st.stop()

    # ------------------ Load & Append CSVs ------------------
    df_r = pd.concat([pd.read_csv(file) for file in csv_files], ignore_index=True)

    # ------------------ Cleaning ------------------
    required_cols = [
        'Test_date_time','Profile_id','Patient_id','Test_result','Test_status',
        'Lab_name','User_name','Sample_type','Truelab_id','Lot',
        'Chip_serial_no','Ct1','Ct2','Ct3','Load1','Load2','Load3',
        'Bayno','Chip_batchno','Result_recieved_date'
    ]

    df_r = df_r[required_cols]
    df_r = df_r[df_r['User_name'] != 'Service']

    df_r['Lab_name'] = df_r['Lab_name'].str.upper().str.strip()
    df_r['Lot'] = df_r['Lot'].str.upper().str.replace(" ", "", regex=False)

    df_r['Test_date_time'] = pd.to_datetime(df_r['Test_date_time'], errors='coerce')
    df_r['Result_recieved_date'] = pd.to_datetime(df_r['Result_recieved_date'], errors='coerce')

    for col in ['Ct1','Ct2','Ct3']:
        df_r[col] = pd.to_numeric(df_r[col], errors='coerce')

    df_r['Truelab_id'] = (
        df_r['Truelab_id']
        .astype(str).str.split('-').str[0]
        .str.upper().str.strip()
    )

    # ------------------ Run Summary ------------------
    runs_summary = (
        df_r.groupby('Truelab_id')
        .agg(
            Total_Runs=('Patient_id', 'count'),
            Last_Run_Date=('Test_date_time', 'max'),
            Lab_name_Dashboard=('Lab_name', 'last')
        )
        .reset_index()
    )

    # ------------------ Master File ------------------
    mst = pd.read_excel(master_file)
    mst.columns = mst.columns.str.strip()

    mst['Truelab_id'] = (
        mst['Serial / Batch ID: Serial / Batch #']
        .astype(str).str.split('-').str[0]
        .str.upper().str.strip()
    )

    mst = mst.rename(columns={
        'Account Name': 'Lab_name_Masterlist',
        'Billing State/Province': 'State',
        'Account Owner: Full Name': 'Account Owner',
        'Type': 'Customer Type'
    })

    mst = mst[['Zone','Lab_name_Masterlist','State','Account Owner','Customer Type','Truelab_id']]
    mst['Lab_name_Masterlist'] = mst['Lab_name_Masterlist'].str.upper().str.strip()

    # ------------------ Merge ------------------
    final = pd.merge(mst, runs_summary, on='Truelab_id', how='left')
    final['Status'] = np.where(final['Total_Runs'].isna(), 'Inactive', 'Active')
    final['Total_Runs'] = final['Total_Runs'].fillna(0).astype(int)

    final = final.reset_index()
    final = final[
        ['index','Zone','Lab_name_Masterlist','State','Account Owner',
         'Customer Type','Truelab_id','Lab_name_Dashboard',
         'Last_Run_Date','Total_Runs','Status']
    ]

    # ------------------ Summary ------------------
    active_df = final[final['Status'] == 'Active']
    inactive_df = final[final['Status'] == 'Inactive']

    active_summary = active_df.groupby(['State','Customer Type']).size().reset_index(name='Active_Count')
    inactive_summary = inactive_df.groupby(['State','Customer Type']).size().reset_index(name='Inactive_Count')

    summary = pd.merge(
        active_summary,
        inactive_summary,
        on=['State','Customer Type'],
        how='outer'
    ).fillna(0)

    summary['Total_Count'] = summary['Active_Count'] + summary['Inactive_Count']

    # ------------------ Export ------------------
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        final.to_excel(writer, sheet_name="Detailed Connectivity", index=False)
        summary.to_excel(writer, sheet_name="State wise connectivity", index=False)

    # ------------------ FINAL UI ------------------
    st.success("✅ All files processed successfully.")

    st.download_button(
        "⬇ Download Final Connectivity Output",
        data=output.getvalue(),
        file_name="Final_Connectivity_Output.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
