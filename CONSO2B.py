import streamlit as st
import pandas as pd
import numpy as np
import os
from io import BytesIO
from typing import List, Dict, Tuple, Optional
import traceback

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="CONSO2B Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM STYLING
# ============================================================================
st.markdown("""
<style>
    /* Main container styling */
    .main {
        padding: 1rem 2rem;
    }
    
    /* Button styling */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    
    /* Info boxes */
    .info-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #2196f3;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .success-box {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #4caf50;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .warning-box {
        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #ff9800;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Headers */
    h1 {
        color: #1a237e;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: #283593;
        font-weight: 600;
        margin-top: 2rem;
    }
    
    h3 {
        color: #3949ab;
        font-weight: 600;
        margin-top: 1.5rem;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    
    /* Upload box */
    [data-testid="stFileUploader"] {
        border: 2px dashed #667eea;
        border-radius: 10px;
        padding: 2rem;
        background: #f8f9ff;
    }
    
    /* Dataframe styling */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Progress bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CONSTANTS
# ============================================================================
EXCEL_EXTENSIONS = (".xls", ".xlsx", ".xlsm", ".xlsb")
CSV_EXTENSIONS = (".csv",)
SUPPORTED_EXTENSIONS = EXCEL_EXTENSIONS + CSV_EXTENSIONS

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
def init_session_state():
    """Initialize all session state variables"""
    if 'page' not in st.session_state:
        st.session_state.page = 'upload'
    if 'files_data' not in st.session_state:
        st.session_state.files_data = []
    if 'all_sheets' not in st.session_state:
        st.session_state.all_sheets = []
    if 'selected_sheets' not in st.session_state:
        st.session_state.selected_sheets = []
    if 'consolidated_df' not in st.session_state:
        st.session_state.consolidated_df = None
    if 'selected_columns' not in st.session_state:
        st.session_state.selected_columns = []
    if 'processing_logs' not in st.session_state:
        st.session_state.processing_logs = []
    if 'file_sheet_mapping' not in st.session_state:
        st.session_state.file_sheet_mapping = {}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def add_log(message: str, log_type: str = "info"):
    """Add message to processing log"""
    icon_map = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌"
    }
    icon = icon_map.get(log_type, "ℹ️")
    st.session_state.processing_logs.append(f"{icon} {message}")

def clear_logs():
    """Clear all processing logs"""
    st.session_state.processing_logs = []

def sanitize_column_name(col, index: int) -> str:
    """
    Sanitize column name to ensure it's a valid string
    """
    if col is None or (isinstance(col, float) and np.isnan(col)):
        return f"Column_{index}"
    
    col_str = str(col).strip()
    if not col_str or col_str.lower() in ['nan', 'none', '']:
        return f"Column_{index}"
    
    return col_str

def make_unique_columns(cols: List) -> List[str]:
    """
    Make column labels unique by appending suffixes to duplicates
    """
    seen = {}
    unique_cols = []
    
    for idx, col in enumerate(cols):
        # Sanitize the column name
        clean_col = sanitize_column_name(col, idx)
        
        # Make it unique if duplicate
        if clean_col not in seen:
            seen[clean_col] = 0
            unique_cols.append(clean_col)
        else:
            seen[clean_col] += 1
            unique_cols.append(f"{clean_col}_{seen[clean_col]}")
    
    return unique_cols

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean dataframe by removing empty rows/columns and filling NaN values
    """
    # Remove completely empty rows and columns
    df = df.dropna(axis=0, how='all')
    df = df.dropna(axis=1, how='all')
    
    # Fill remaining NaN with '-'
    df = df.fillna('-')
    
    # Reset index
    df = df.reset_index(drop=True)
    
    # Clean column names
    df.columns = make_unique_columns(df.columns)
    
    return df

# ============================================================================
# HEADER DETECTION FUNCTIONS
# ============================================================================
def check_two_row_header(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Check if rows 5 and 6 contain multi-level headers (Invoice/Tax details)
    and merge them if found
    """
    if df.shape[0] < 6:
        return None
    
    try:
        row4 = df.iloc[4].fillna("")
        row5 = df.iloc[5].fillna("")
        
        # Convert to strings and check for markers
        row4_texts = [str(x).lower() for x in row4]
        marker_found = any("invoice details" in t or "tax details" in t for t in row4_texts)
        
        if marker_found:
            combined_headers = []
            for i in range(len(row4)):
                main = sanitize_column_name(row4.iloc[i], i)
                sub = sanitize_column_name(row5.iloc[i], i)
                
                # Create combined header
                if main and sub and main != f"Column_{i}" and sub != f"Column_{i}":
                    combined_headers.append(f"{main}_{sub}")
                elif main and main != f"Column_{i}":
                    combined_headers.append(main)
                elif sub and sub != f"Column_{i}":
                    combined_headers.append(sub)
                else:
                    combined_headers.append(f"Column_{i}")
            
            # Create new dataframe starting from row 7
            df_new = df.iloc[6:].copy()
            df_new.columns = make_unique_columns(combined_headers)
            df_new = clean_dataframe(df_new)
            
            return df_new
    except Exception as e:
        add_log(f"Error in two-row header detection: {str(e)}", "warning")
        return None
    
    return None

def find_header_row(df: pd.DataFrame, search_text: str = "GSTIN of supplier") -> Optional[int]:
    """
    Find the row containing the header by searching for a specific text
    """
    try:
        for idx in range(min(20, len(df))):  # Search first 20 rows only
            row = df.iloc[idx]
            for cell in row:
                if pd.notna(cell) and search_text.lower() in str(cell).lower():
                    return idx
    except Exception as e:
        add_log(f"Error finding header row: {str(e)}", "warning")
    
    return None

# ============================================================================
# FILE READING FUNCTIONS
# ============================================================================
def read_file_with_header(file_content: bytes, sheet_name: Optional[str], 
                          file_name: str) -> pd.DataFrame:
    """
    Read file and intelligently detect headers
    """
    ext = os.path.splitext(file_name)[1].lower()
    
    try:
        # Read file without header first
        if ext in CSV_EXTENSIONS:
            df_raw = pd.read_csv(BytesIO(file_content), header=None, dtype=str, 
                                encoding='utf-8', on_bad_lines='skip')
        else:
            df_raw = pd.read_excel(BytesIO(file_content), sheet_name=sheet_name, 
                                  header=None, dtype=str)
        
        # Try two-row header detection first
        df_processed = check_two_row_header(df_raw)
        if df_processed is not None:
            add_log(f"Detected two-row header in {file_name}", "success")
            return df_processed
        
        # Try to find standard header row
        header_idx = find_header_row(df_raw)
        if header_idx is not None:
            # Extract header and data
            headers = df_raw.iloc[header_idx].tolist()
            headers = make_unique_columns(headers)
            
            df = df_raw.iloc[header_idx + 1:].copy()
            df.columns = headers
            df = clean_dataframe(df)
            
            add_log(f"Found header at row {header_idx + 1} in {file_name}", "success")
            return df
        
        # If no special header found, read normally
        if ext in CSV_EXTENSIONS:
            df = pd.read_csv(BytesIO(file_content), dtype=str, encoding='utf-8', 
                           on_bad_lines='skip')
        else:
            df = pd.read_excel(BytesIO(file_content), sheet_name=sheet_name, dtype=str)
        
        df.columns = make_unique_columns(df.columns)
        df = clean_dataframe(df)
        
        add_log(f"Loaded {file_name} with default header", "info")
        return df
        
    except Exception as e:
        raise Exception(f"Error reading {file_name}: {str(e)}")

def get_sheet_names(file_content: bytes, file_name: str) -> List[str]:
    """
    Get list of sheet names from Excel file or return ['CSV'] for CSV files
    """
    ext = os.path.splitext(file_name)[1].lower()
    
    if ext in CSV_EXTENSIONS:
        return ["CSV"]
    
    try:
        xls = pd.ExcelFile(BytesIO(file_content))
        return xls.sheet_names
    except Exception as e:
        add_log(f"Error reading sheets from {file_name}: {str(e)}", "error")
        return []

# ============================================================================
# DATA CONSOLIDATION
# ============================================================================
def consolidate_data(files_data: List[Dict], selected_sheets: List[str]) -> pd.DataFrame:
    """
    Consolidate data from multiple files and sheets
    """
    all_dataframes = []
    total_operations = len(files_data) * len(selected_sheets)
    current_operation = 0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for file_data in files_data:
        file_name = file_data['name']
        file_content = file_data['content']
        ext = os.path.splitext(file_name)[1].lower()
        
        # Get available sheets for this file
        available_sheets = get_sheet_names(file_content, file_name)
        
        for sheet_name in selected_sheets:
            current_operation += 1
            progress = current_operation / total_operations
            progress_bar.progress(progress)
            status_text.text(f"Processing: {file_name} - {sheet_name}")
            
            # Check if sheet exists in this file
            if sheet_name not in available_sheets:
                add_log(f"Sheet '{sheet_name}' not found in {file_name}", "warning")
                continue
            
            try:
                # Read the sheet
                df = read_file_with_header(file_content, sheet_name, file_name)
                
                if df is not None and not df.empty:
                    # Add metadata columns
                    df.insert(0, 'SourceFile', file_name)
                    df.insert(1, 'SheetName', sheet_name)
                    
                    all_dataframes.append(df)
                    add_log(f"✓ Loaded {file_name} - {sheet_name}: {len(df)} rows", "success")
                else:
                    add_log(f"No data in {file_name} - {sheet_name}", "warning")
                    
            except Exception as e:
                add_log(f"✗ Error loading {file_name} - {sheet_name}: {str(e)}", "error")
                continue
    
    progress_bar.empty()
    status_text.empty()
    
    if not all_dataframes:
        raise Exception("No data could be loaded from the selected files and sheets")
    
    # Concatenate all dataframes
    consolidated = pd.concat(all_dataframes, ignore_index=True, sort=False)
    
    # Fill any NaN created during concatenation
    consolidated = consolidated.fillna('-')
    
    add_log(f"✓ Consolidation complete: {len(consolidated)} total rows", "success")
    
    return consolidated

# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================
def export_to_excel(df: pd.DataFrame, split_by_sheet: bool = False) -> BytesIO:
    """
    Export dataframe to Excel format
    """
    output = BytesIO()
    
    try:
        if split_by_sheet and 'SheetName' in df.columns:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Group by SheetName and write to separate sheets
                for sheet_name, group_df in df.groupby('SheetName'):
                    # Sanitize sheet name (Excel has 31 char limit)
                    safe_sheet_name = str(sheet_name)[:31]
                    safe_sheet_name = safe_sheet_name.replace('/', '_').replace('\\', '_')
                    
                    group_df.to_excel(writer, sheet_name=safe_sheet_name, 
                                    index=False, freeze_panes=(1, 0))
        else:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Consolidated', 
                          index=False, freeze_panes=(1, 0))
        
        output.seek(0)
        return output
    except Exception as e:
        raise Exception(f"Error exporting to Excel: {str(e)}")

def export_to_csv(df: pd.DataFrame) -> str:
    """
    Export dataframe to CSV format
    """
    try:
        return df.to_csv(index=False, encoding='utf-8-sig')
    except Exception as e:
        raise Exception(f"Error exporting to CSV: {str(e)}")

# ============================================================================
# UI COMPONENTS
# ============================================================================
def render_sidebar():
    """Render sidebar with navigation and info"""
    with st.sidebar:
        # Assuming you have an image at "assets/my_logo.png"
        # If not, you can comment out or delete the next line
        st.image("assets/my_logo.png", use_container_width=True)
        
        st.markdown("---")
        
        # Navigation
        st.markdown("### 📋 Navigation")
        
        pages = {
            'upload': '📁 Upload Files',
            'sheets': '📋 Select Sheets',
            'consolidate': '🔄 Consolidate & Export'
        }
        
        for key, label in pages.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()
        
        st.markdown("---")
        
        # Status indicators
        st.markdown("### 📊 Status")
        st.metric("Files Loaded", len(st.session_state.files_data))
        st.metric("Sheets Available", len(st.session_state.all_sheets))
        st.metric("Sheets Selected", len(st.session_state.selected_sheets))
        
        if st.session_state.consolidated_df is not None:
            st.metric("Total Rows", len(st.session_state.consolidated_df))
        
        st.markdown("---")
        
        # Help section
        with st.expander("ℹ️ About XLMERGE"):
            st.markdown("""
            **XLMERGE** consolidates GSTR 2B data from multiple files into one.
            
            **Features:**
            - Smart header detection
            - Multi-file processing
            - Data cleaning & validation
            - Flexible export options
            
            **Supported Formats:**
            - Excel (.xls, .xlsx, .xlsm, .xlsb)
            - CSV (.csv)
            """)

        # User Guide Section
        with st.expander("📖 User Guide"):
            st.markdown("""
            **1. Upload Files:**
            Select one or more of your monthly or quarterly GSTR-2B files. The data will be consolidated in the order you upload them.

            **2. Extract & Select Sheets:**
            Click **`Extract Sheet Names`**, then **`Next: Select Sheets →`**. Choose the sheets you want to merge and click **`Next: Consolidate →`**.

            **3. Consolidate & Customize:**
            Click **`🔄 Start Consolidation`**. After processing, select the specific columns you want in your final report.

            **4. Download Your Report:**
            Choose your export format. By default, data is combined into a single sheet. To create separate worksheets for each original sheet name, check the **`Split data by sheet`** box. Finally, click **`📥 Generate Export File`**.
            """)
        
        # Creators Section
        with st.expander("👥 Creators"):
            st.markdown("""
            - **Created by:** Nandeesh B
            - **Guidance:** CA Rajashekaran
            """)

        st.markdown("---")
        
        # Reset button with a unique key
        if st.button("🔄 Reset All", type="secondary", use_container_width=True, key="reset_all_sidebar"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            init_session_state()
            st.rerun()
        
        st.markdown("---")
        
        # Status indicators
        st.markdown("### 📊 Status")
        st.metric("Files Loaded", len(st.session_state.files_data))
        st.metric("Sheets Available", len(st.session_state.all_sheets))
        st.metric("Sheets Selected", len(st.session_state.selected_sheets))
        
        if st.session_state.consolidated_df is not None:
            st.metric("Total Rows", len(st.session_state.consolidated_df))
        
        st.markdown("---")
        
        # Help section
        with st.expander("ℹ️ About CONSO2B"):
            st.markdown("""
            **CONSO2B** consolidates GSTR 2B data from multiple files into one.
            
            **Features:**
            - Smart header detection
            - Multi-file processing
            - Data cleaning & validation
            - Flexible export options
            
            **Supported Formats:**
            - Excel (.xls, .xlsx, .xlsm, .xlsb)
            - CSV (.csv)
            """)
        
        st.markdown("---")
        
        # Reset button
        if st.button("🔄 Reset All", type="secondary", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            init_session_state()
            st.rerun()

# ============================================================================
# PAGE 1: UPLOAD FILES
# ============================================================================
def page_upload():
    """File upload page"""
    st.title("📁 Upload Files")
    
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("""
    **Step 1: Upload your GSTR 2B files**
    
    - Select one or more Excel or CSV files
    - Files can be from different tax periods
    - Upload the files in order to get the GSTR2B Conso in order
    - All supported formats will be processed
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Drop files here or click to browse",
        type=['xls', 'xlsx', 'xlsm', 'xlsb', 'csv'],
        accept_multiple_files=True,
        help="Select multiple files by holding Ctrl (Windows) or Cmd (Mac)"
    )
    
    if uploaded_files:
        # Process uploaded files
        st.session_state.files_data = []
        
        for file in uploaded_files:
            file_data = {
                'name': file.name,
                'content': file.read(),
                'size': file.size,
                'type': file.type
            }
            st.session_state.files_data.append(file_data)
        
        # Display uploaded files
        st.markdown("---")
        st.subheader(f"📂 Uploaded Files ({len(st.session_state.files_data)})")
        
        for idx, file_data in enumerate(st.session_state.files_data):
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                
                with col1:
                    st.markdown(f"**{idx + 1}. {file_data['name']}**")
                
                with col2:
                    size_kb = file_data['size'] / 1024
                    size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                    st.text(size_str)
                
                with col3:
                    ext = os.path.splitext(file_data['name'])[1].upper()
                    st.text(ext)
                
                with col4:
                    if st.button("🗑️", key=f"delete_{idx}"):
                        st.session_state.files_data.pop(idx)
                        st.rerun()
        
        st.markdown("---")
        
        # Action buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📋 Extract Sheet Names", type="primary", 
                        use_container_width=True):
                try:
                    with st.spinner("Analyzing files..."):
                        all_sheets = set()
                        file_sheet_map = {}
                        
                        for file_data in st.session_state.files_data:
                            sheets = get_sheet_names(file_data['content'], 
                                                    file_data['name'])
                            all_sheets.update(sheets)
                            file_sheet_map[file_data['name']] = sheets
                        
                        st.session_state.all_sheets = sorted(list(all_sheets))
                        st.session_state.file_sheet_mapping = file_sheet_map
                        st.session_state.selected_sheets = []
                        
                        st.success(f"✅ Found {len(st.session_state.all_sheets)} unique sheet(s)")
                        st.balloons()
                        
                except Exception as e:
                    st.error(f"❌ Error analyzing files: {str(e)}")
        
        with col2:
            if len(st.session_state.all_sheets) > 0:
                if st.button("Next: Select Sheets →", use_container_width=True):
                    st.session_state.page = 'sheets'
                    st.rerun()
    
    else:
        st.info("👆 Upload files to begin")

# ============================================================================
# PAGE 2: SELECT SHEETS
# ============================================================================
def page_sheets():
    """Sheet selection page"""
    
    if not st.session_state.files_data:
        st.warning("⚠️ Please upload files first")
        if st.button("← Go to Upload"):
            st.session_state.page = 'upload'
            st.rerun()
        return
    
    if not st.session_state.all_sheets:
        st.warning("⚠️ Please extract sheet names first")
        if st.button("← Go to Upload"):
            st.session_state.page = 'upload'
            st.rerun()
        return
    
    st.title("📋 Select Sheets to Process")
    
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("""
    **Step 2: Choose which sheets to include**
    
    - Select sheets that contain the data you want to consolidate
    - Only selected sheets will be processed
    - Sheet availability varies by file
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Quick selection buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Select All", use_container_width=True):
            st.session_state.selected_sheets = st.session_state.all_sheets.copy()
            st.rerun()
    
    with col2:
        if st.button("❌ Deselect All", use_container_width=True):
            st.session_state.selected_sheets = []
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset Selection", use_container_width=True):
            st.session_state.selected_sheets = []
            st.rerun()
    
    st.markdown("---")
    
    # Display sheets with file availability
    st.subheader("Available Sheets")
    
    # Initialize selected sheets if empty
    if not st.session_state.selected_sheets:
        st.session_state.selected_sheets = []
    
    # Create two columns for sheet display
    col1, col2 = st.columns(2)
    
    for idx, sheet_name in enumerate(st.session_state.all_sheets):
        # Count how many files have this sheet
        file_count = sum(1 for files in st.session_state.file_sheet_mapping.values() 
                        if sheet_name in files)
        
        with col1 if idx % 2 == 0 else col2:
            is_selected = st.checkbox(
                f"{sheet_name} ({file_count} file{'s' if file_count != 1 else ''})",
                value=sheet_name in st.session_state.selected_sheets,
                key=f"sheet_{idx}_{sheet_name}"
            )
            
            if is_selected and sheet_name not in st.session_state.selected_sheets:
                st.session_state.selected_sheets.append(sheet_name)
            elif not is_selected and sheet_name in st.session_state.selected_sheets:
                st.session_state.selected_sheets.remove(sheet_name)
    
    st.markdown("---")
    
    # Summary and navigation
    st.info(f"**Selected: {len(st.session_state.selected_sheets)} / {len(st.session_state.all_sheets)} sheets**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("← Back to Upload", use_container_width=True):
            st.session_state.page = 'upload'
            st.rerun()
    
    with col2:
        if len(st.session_state.selected_sheets) > 0:
            if st.button("Next: Consolidate →", type="primary", 
                        use_container_width=True):
                st.session_state.page = 'consolidate'
                st.rerun()
        else:
            st.button("Select at least one sheet", disabled=True, 
                     use_container_width=True)

# ============================================================================
# PAGE 3: CONSOLIDATE & EXPORT
# ============================================================================
def page_consolidate():
    """Consolidation and export page"""
    
    if not st.session_state.files_data:
        st.warning("⚠️ Please upload files first")
        if st.button("← Go to Upload"):
            st.session_state.page = 'upload'
            st.rerun()
        return
    
    if not st.session_state.selected_sheets:
        st.warning("⚠️ Please select sheets first")
        if st.button("← Go to Sheet Selection"):
            st.session_state.page = 'sheets'
            st.rerun()
        return
    
    st.title("🔄 Consolidate & Export Data")
    
    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("""
    **Step 3: Process and export your data**
    
    - Click Consolidate to merge all selected data
    - Review the consolidated data
    - Choose columns to export
    - Download in your preferred format
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Consolidate button
    if st.button("🔄 Start Consolidation", type="primary", use_container_width=True):
        clear_logs()
        
        try:
            with st.spinner("Processing files..."):
                consolidated = consolidate_data(
                    st.session_state.files_data,
                    st.session_state.selected_sheets
                )
                
                st.session_state.consolidated_df = consolidated
                # Default to only the essential columns being selected
                st.session_state.selected_columns = ['SourceFile', 'SheetName']
                
            st.success("✅ Consolidation completed successfully!")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ Consolidation failed: {str(e)}")
            add_log(f"Consolidation error: {str(e)}", "error")
    
    # Show logs if available
    if st.session_state.processing_logs:
        with st.expander("📋 Processing Log", expanded=False):
            for log in st.session_state.processing_logs:
                st.text(log)
    
    # If data is consolidated, show preview and export options
    if st.session_state.consolidated_df is not None:
        df = st.session_state.consolidated_df
        
        st.markdown("---")
        st.markdown("### 📊 Consolidated Data Summary")
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Rows", f"{len(df):,}")
        
        with col2:
            st.metric("Total Columns", len(df.columns))
        
        with col3:
            unique_sheets = df['SheetName'].nunique() if 'SheetName' in df.columns else 0
            st.metric("Unique Sheets", unique_sheets)
        
        with col4:
            memory_mb = df.memory_usage(deep=True).sum() / 1024 / 1024
            st.metric("Memory Usage", f"{memory_mb:.2f} MB")
        
        # Data Preview
        st.markdown("---")
        st.markdown("### 👁️ Data Preview (First 20 rows)")
        
        preview_df = df.head(20).copy()
        st.dataframe(
            preview_df,
            use_container_width=True,
            height=400
        )
        
        # Column Selection
        st.markdown("---")
        st.markdown("### 🎯 Select Columns to Export")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("✅ Select All Columns", use_container_width=True):
                st.session_state.selected_columns = list(df.columns)
                st.rerun()
        
        with col2:
            if st.button("❌ Deselect All", use_container_width=True):
                # Keep SourceFile and SheetName always selected
                st.session_state.selected_columns = ['SourceFile', 'SheetName']
                st.rerun()
        
        with col3:
            if st.button("🔄 Reset to Default", use_container_width=True):
                st.session_state.selected_columns = ['SourceFile', 'SheetName']
                st.rerun()
        
        st.markdown("---")
        
        # Display columns in a grid
        all_columns = list(df.columns)
        
        # Calculate number of rows needed (4 columns per row)
        cols_per_row = 4
        num_rows = (len(all_columns) + cols_per_row - 1) // cols_per_row
        
        for row in range(num_rows):
            cols = st.columns(cols_per_row)
            
            for col_idx in range(cols_per_row):
                list_idx = row * cols_per_row + col_idx
                
                if list_idx < len(all_columns):
                    col_name = all_columns[list_idx]
                    
                    with cols[col_idx]:
                        # Force SourceFile and SheetName to always be selected
                        if col_name in ['SourceFile', 'SheetName']:
                            is_selected = st.checkbox(
                                f"🔒 {col_name}",
                                value=True,
                                disabled=True,
                                key=f"col_{list_idx}",
                                help="This column is always included"
                            )
                        else:
                            is_selected = st.checkbox(
                                col_name,
                                value=col_name in st.session_state.selected_columns,
                                key=f"col_{list_idx}"
                            )
                        
                        # Update selected columns
                        if is_selected and col_name not in st.session_state.selected_columns:
                            st.session_state.selected_columns.append(col_name)
                        elif not is_selected and col_name in st.session_state.selected_columns:
                            if col_name not in ['SourceFile', 'SheetName']:
                                st.session_state.selected_columns.remove(col_name)
        
        st.markdown("---")
        st.info(f"**Selected Columns: {len(st.session_state.selected_columns)} / {len(all_columns)}**")
        
        # Export Section
        st.markdown("---")
        st.markdown("### 💾 Export Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            export_format = st.selectbox(
                "Select Export Format",
                ["Excel (XLSX)", "Excel (XLS)", "CSV"],
                help="Choose the format for your exported file"
            )
        
        with col2:
            split_by_sheet = st.checkbox(
                "📑 Split data by sheet",
                value=True,
                help="Create separate worksheets for each sheet (Excel only)"
            )
        
        # Preview export data
        if len(st.session_state.selected_columns) > 0:
            # Get the original column order from the main dataframe
            original_order = list(df.columns)
            # Create a new list of selected columns that respects the original order
            ordered_selection = [col for col in original_order if col in st.session_state.selected_columns]

            export_df = df[ordered_selection].copy()
            
            
            st.markdown("---")
            
            # Export button
            if st.button("📥 Generate Export File", type="primary", use_container_width=True):
                try:
                    with st.spinner("Generating file..."):
                        
                        if "Excel" in export_format:
                            # Export to Excel
                            output = export_to_excel(export_df, split_by_sheet)
                            
                            file_ext = "xlsx" if "XLSX" in export_format else "xls"
                            file_name = f"consolidated_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
                            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            
                            st.download_button(
                                label=f"⬇️ Download {file_ext.upper()} File",
                                data=output,
                                file_name=file_name,
                                mime=mime_type,
                                use_container_width=True
                            )
                            
                        else:
                            # Export to CSV
                            csv_data = export_to_csv(export_df)
                            file_name = f"consolidated_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
                            
                            st.download_button(
                                label="⬇️ Download CSV File",
                                data=csv_data,
                                file_name=file_name,
                                mime="text/csv",
                                use_container_width=True
                            )
                        
                        st.success("✅ File ready for download!")
                        
                except Exception as e:
                    st.error(f"❌ Export failed: {str(e)}")
        
        else:
            st.warning("⚠️ Please select at least one column to export")
        
        # Additional Info
        st.markdown("---")
        st.markdown("### 📝 Export Notes")
        
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown("""
        **Important Information:**
        
        - **SourceFile** and **SheetName** columns are always included for traceability
        - **Split by Sheet** option creates separate worksheets in Excel (one per sheet)
        - **CSV format** will export all data in a single file
        - **Date/Time** is added to filename to prevent overwriting
        - All empty cells are filled with **'-'** for consistency
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Navigation
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("← Back to Sheets", use_container_width=True):
                st.session_state.page = 'sheets'
                st.rerun()
        
        with col2:
            if st.button("🔄 Process Again", use_container_width=True):
                st.session_state.consolidated_df = None
                st.session_state.selected_columns = []
                clear_logs()
                st.rerun()
        
        with col3:
            if st.button("🏠 Start Over", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                init_session_state()
                st.rerun()

# ============================================================================
# MAIN APPLICATION
# ============================================================================
def main():
    """Main application entry point"""
    
    # Initialize session state
    init_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Main content area with header
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("""
        # 📊 CONSO2B
        ### GSTR 2B Data Consolidation Tool
        """)
    
    with col2:
        st.markdown("""
        <div style='text-align: right; padding-top: 20px;'>
            <p style='color: #666; font-size: 0.9em;'>
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Route to appropriate page
    if st.session_state.page == 'upload':
        page_upload()
    elif st.session_state.page == 'sheets':
        page_sheets()
    elif st.session_state.page == 'consolidate':
        page_consolidate()
    else:
        st.session_state.page = 'upload'
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p></p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# RUN APPLICATION
# ============================================================================
if __name__ == "__main__":

    main()



