import streamlit as st
import psycopg2

# --- DB connection ---
conn = psycopg2.connect(
    host="localhost",
    database="postgres",
    user="postgres",
    password="1234"
)
cursor = conn.cursor()

# --- ENUM Utilities ---

def get_enum_values(enum_name):
    try:
        cursor.execute("""
            SELECT enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname = %s
            ORDER BY e.enumsortorder;
        """, (enum_name,))
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        conn.rollback()
        st.error(f"Error fetching enum values: {e}")
        return []

def get_all_enum_types():
    try:
        cursor.execute("""
            SELECT DISTINCT t.typname
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid;
        """)
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        conn.rollback()
        st.error(f"Error fetching enum types: {e}")
        return []

def add_enum_value(enum_name, new_value):
    try:
        cursor.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS %s;", (new_value,))
        conn.commit()
        return True, "Value added successfully!"
    except Exception as e:
        conn.rollback()
        return False, str(e)

# --- UI Layout ---
st.set_page_config(page_title="Scan Manager", layout="wide")
tab1, tab2 = st.tabs(["➕ Add New Scan", "🛠 Edit ENUMs"])

# ---------------------
# TAB 1: Add New Scan
# ---------------------
with tab1:
    st.header("Add New Scan to PostgreSQL")

    with st.form("scan_form"):
        col1, col2 = st.columns(2)

        with col1:
            specimen = st.text_input("Specimen")
            accession_num = st.text_input("Accession #")
            kingdom = st.text_input("Kingdom")
            low_taxon = st.text_input("Low-level Taxon")
            mid_taxon = st.text_input("Mid-level Taxon")
            high_taxon = st.text_input("High-level Taxon")
            family = st.text_input("Family")

        with col2:
            species = st.text_input("Species")
            habitat = st.text_input("Habitat")
            scanner = st.selectbox("Scanner", get_enum_values("scanner_enum"))
            museum_dept = st.selectbox("Museum Department", get_enum_values("museum_dept_enum"))
            accession_year = st.selectbox("Accession Year", get_enum_values("accession_year_enum"))
            continent = st.selectbox("Continent", get_enum_values("continent_enum"))
            preservation_method = st.selectbox("Preservation Method", get_enum_values("preservation_method_enum"))
            sex = st.selectbox("Sex", get_enum_values("sex_enum"))
            growth_stage = st.selectbox("Growth Stage", get_enum_values("growth_stage_enum"))
            material = st.selectbox("Material", get_enum_values("material_enum"))
            bones_cartilage = st.selectbox("Bones / Cartilage", get_enum_values("bones_cartilage_enum"))
            teeth = st.selectbox("Teeth", get_enum_values("teeth_enum"))
            keratin = st.selectbox("Keratin", get_enum_values("keratin_enum"))
            object_type = st.selectbox("Object", get_enum_values("object_enum"))
            time_period = st.selectbox("Time Period", get_enum_values("time_period_enum"))
            civilization = st.selectbox("Civilization", get_enum_values("civilization_enum"))

        submitted = st.form_submit_button("Submit")
        if submitted:
            try:
                cursor.execute("""
                    INSERT INTO Scans (
                        specimen, accession_#, kingdom, low_level_taxon, mid_level_taxon, high_level_taxon,
                        family, species, habitat, scanner, museum_dept, accession_year,
                        continent, preservation_method, sex, growth_stage, material, bones_cartilage,
                        teeth, keratin, object, "time period", civilization
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    specimen, accession_num, kingdom, low_taxon, mid_taxon, high_taxon,
                    family, species, habitat, scanner, museum_dept, accession_year,
                    continent, preservation_method, sex, growth_stage, material, bones_cartilage,
                    teeth, keratin, object_type, time_period, civilization
                ))
                conn.commit()
                st.success("Scan added successfully!")
            except Exception as e:
                conn.rollback()
                st.error(f"Error inserting scan: {e}")

# ---------------------
# TAB 2: Edit ENUMs
# ---------------------
with tab2:
    st.header("Edit ENUM Types")

    enum_type = st.selectbox("Select ENUM Type", get_all_enum_types())
    current_values = get_enum_values(enum_type)
    st.markdown("**Current Values:** " + ", ".join(current_values))

    new_value = st.text_input("New Value to Add")
    if st.button("Add Value to ENUM"):
        if new_value.strip() == "":
            st.warning("Please enter a non-empty value.")
        else:
            success, message = add_enum_value(enum_type, new_value.strip())
            if success:
                st.success(message)
            else:
                st.error(message)