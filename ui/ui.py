from __future__ import annotations

import time

import requests
import streamlit as st


API_URL = "http://127.0.0.1:8000"


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Natural Language Insights",
    page_icon="📊",
    layout="wide",
)


# ============================================================
# SESSION STATE
# ============================================================

if "dataset_id" not in st.session_state:
    st.session_state["dataset_id"] = None

if "upload_result" not in st.session_state:
    st.session_state["upload_result"] = None

if "ingestion_job_id" not in st.session_state:
    st.session_state["ingestion_job_id"] = None

if "dataset_ready" not in st.session_state:
    st.session_state["dataset_ready"] = False

if "selected_question" not in st.session_state:
    st.session_state["selected_question"] = ""


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def upload_dataset(uploaded_file):
    """
    Upload CSV to FastAPI.

    The backend returns:
    - dataset_id
    - ingestion job_id
    - status
    """

    response = requests.post(
        f"{API_URL}/datasets",
        files={
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "text/csv",
            )
        },
        timeout=300,
    )

    if response.status_code >= 400:

        try:
            detail = response.json().get(
                "detail",
                "Upload failed.",
            )
        except Exception:
            detail = "Upload failed."

        raise RuntimeError(str(detail))

    return response.json()


def get_job(job_id: str):
    """
    Retrieve the status of an asynchronous job.
    """

    response = requests.get(
        f"{API_URL}/jobs/{job_id}",
        timeout=30,
    )

    if response.status_code >= 400:

        try:
            detail = response.json().get(
                "detail",
                "Could not retrieve job.",
            )
        except Exception:
            detail = "Could not retrieve job."

        raise RuntimeError(str(detail))

    return response.json()


def wait_for_ingestion(job_id: str):
    """
    Poll the dataset ingestion job until it completes.
    """

    status_placeholder = st.empty()

    while True:

        job = get_job(job_id)

        status = job.get("status")

        if status == "queued":

            status_placeholder.info(
                "⏳ Dataset is queued for processing..."
            )

        elif status == "running":

            status_placeholder.info(
                "⚙️ Loading CSV and building DuckDB..."
            )

        elif status == "completed":

            status_placeholder.success(
                "✅ Dataset is ready."
            )

            return job

        elif status == "failed":

            error = job.get(
                "error",
                {},
            )

            message = error.get(
                "message",
                "Dataset ingestion failed.",
            )

            raise RuntimeError(message)

        else:

            status_placeholder.warning(
                f"Unknown job status: {status}"
            )

        time.sleep(5)


def wait_for_question(job_id: str):
    """
    Poll the question job until it completes.
    """

    status_placeholder = st.empty()

    while True:

        job = get_job(job_id)

        status = job.get("status")

        if status == "queued":

            status_placeholder.info(
                "⏳ Question is queued..."
            )

        elif status == "running":

            status_placeholder.info(
                "⚙️ Analyzing your question..."
            )

        elif status == "completed":

            status_placeholder.success(
                "✅ Analysis completed."
            )

            return job.get("result")

        elif status == "failed":

            error = job.get(
                "error",
                {},
            )

            message = error.get(
                "message",
                "Question processing failed.",
            )

            raise RuntimeError(message)

        else:

            status_placeholder.warning(
                f"Unknown job status: {status}"
            )

        time.sleep(2)


def reset_dataset():
    """
    Clear the current dataset from the UI session.
    """

    st.session_state["dataset_id"] = None
    st.session_state["upload_result"] = None
    st.session_state["ingestion_job_id"] = None
    st.session_state["dataset_ready"] = False


# ============================================================
# HEADER
# ============================================================

st.title("📊 Natural Language Insights")

st.caption(
    "Upload a CSV and ask analytical questions using natural language."
)


# ============================================================
# SIDEBAR — DATASET UPLOAD
# ============================================================

with st.sidebar:

    st.header("Dataset")

    uploaded_file = st.file_uploader(
        "Upload a CSV file",
        type=["csv"],
        help="Upload a CSV dataset for analysis.",
    )

    if uploaded_file:

        st.write(
            f"**File:** {uploaded_file.name}"
        )

        st.write(
            f"**Size:** "
            f"{uploaded_file.size / (1024 * 1024):.2f} MB"
        )

        if st.button(
            "Upload Dataset",
            use_container_width=True,
            type="primary",
        ):

            try:

                # --------------------------------------------
                # Upload
                # --------------------------------------------

                with st.spinner(
                    "Uploading CSV..."
                ):

                    upload_result = upload_dataset(
                        uploaded_file
                    )

                # --------------------------------------------
                # Save dataset information
                # --------------------------------------------

                dataset_id = upload_result[
                    "dataset_id"
                ]

                ingestion_job_id = upload_result[
                    "job_id"
                ]

                st.session_state[
                    "dataset_id"
                ] = dataset_id

                st.session_state[
                    "upload_result"
                ] = upload_result

                st.session_state[
                    "ingestion_job_id"
                ] = ingestion_job_id

                st.session_state[
                    "dataset_ready"
                ] = False

                # --------------------------------------------
                # Wait for ingestion
                # --------------------------------------------

                ingestion_job = wait_for_ingestion(
                    ingestion_job_id
                )

                # --------------------------------------------
                # Mark dataset ready
                # --------------------------------------------

                if ingestion_job.get(
                    "status"
                ) == "completed":

                    st.session_state[
                        "dataset_ready"
                    ] = True

            except Exception as exc:

                st.error(
                    f"Upload failed: {exc}"
                )

    # --------------------------------------------------------
    # Current dataset status
    # --------------------------------------------------------

    if st.session_state.get(
        "dataset_id"
    ):

        st.divider()

        st.subheader(
            "Current Dataset"
        )

        current_dataset = st.session_state[
            "dataset_id"
        ]

        st.code(
            current_dataset,
            language="text",
        )

        if st.session_state.get(
            "dataset_ready",
            False,
        ):

            st.success(
                "Dataset ready"
            )

        else:

            st.warning(
                "Dataset processing"
            )

        if st.button(
            "Clear Dataset",
            use_container_width=True,
        ):

            reset_dataset()

            st.rerun()


# ============================================================
# DATASET INFORMATION
# ============================================================

dataset_id = st.session_state.get(
    "dataset_id"
)

upload_result = st.session_state.get(
    "upload_result"
)


if dataset_id:

    st.subheader(
        "Dataset Information"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Dataset",
            dataset_id[:8] + "...",
        )

    with col2:

        if upload_result:

            size_bytes = upload_result.get(
                "size_bytes",
                0,
            )

            st.metric(
                "File Size",
                f"{size_bytes / (1024 * 1024):.2f} MB",
            )

        else:

            st.metric(
                "File Size",
                "N/A",
            )

    with col3:

        if st.session_state.get(
            "dataset_ready",
            False,
        ):

            st.metric(
                "Status",
                "Ready",
            )

        else:

            st.metric(
                "Status",
                "Processing",
            )


else:

    st.info(
        "Upload a CSV dataset from the sidebar to begin."
    )


# ============================================================
# QUESTION SECTION
# ============================================================

st.subheader(
    "Ask a Question"
)


# ------------------------------------------------------------
# Example questions
# ------------------------------------------------------------

st.markdown(
    "**Example questions**"
)


examples = [
    "What are the top 10 products by revenue?",
    "Which customers bought only once?",
    "What share of revenue comes from customers who bought only once?",
    "Which products are most frequently bought together?",
    "What was the net revenue in December 2010?",
    "How did revenue growth change from Q1 2011 to Q2 2011 by country?",
]


example_columns = st.columns(3)


for index, example in enumerate(examples):

    with example_columns[
        index % 3
    ]:

        if st.button(
            example,
            key=f"example_{index}",
            use_container_width=True,
        ):

            st.session_state[
                "selected_question"
            ] = example

            st.rerun()


# ------------------------------------------------------------
# Question input
# ------------------------------------------------------------

default_question = st.session_state.get(
    "selected_question",
    "",
)


question = st.text_area(
    "Natural-language question",
    value=default_question,
    placeholder=(
        "Example: What are the top 10 products by revenue?"
    ),
    height=100,
)


# ============================================================
# ASK QUESTION
# ============================================================

ask_button = st.button(
    "🔍 Ask Question",
    type="primary",
    use_container_width=True,
)


if ask_button:

    # --------------------------------------------------------
    # Validate dataset
    # --------------------------------------------------------

    if not dataset_id:

        st.warning(
            "Please upload a CSV dataset first."
        )

    elif not st.session_state.get(
        "dataset_ready",
        False,
    ):

        st.warning(
            "The dataset is still being processed. "
            "Please wait until it is ready."
        )

    # --------------------------------------------------------
    # Validate question
    # --------------------------------------------------------

    elif not question.strip():

        st.warning(
            "Please enter a question."
        )

    else:

        try:

            # ------------------------------------------------
            # Submit question
            # ------------------------------------------------

            with st.spinner(
                "Submitting question..."
            ):

                response = requests.post(
                    f"{API_URL}/questions",
                    json={
                        "dataset_id": dataset_id,
                        "question": question.strip(),
                    },
                    timeout=30,
                )

            if response.status_code >= 400:

                try:

                    detail = response.json().get(
                        "detail",
                        "Question submission failed.",
                    )

                except Exception:

                    detail = (
                        "Question submission failed."
                    )

                raise RuntimeError(
                    str(detail)
                )

            question_job = response.json()

            question_job_id = question_job[
                "job_id"
            ]

            # ------------------------------------------------
            # Poll question job
            # ------------------------------------------------

            result = wait_for_question(
                question_job_id
            )

            if not result:

                st.error(
                    "No result was returned."
                )

            else:

                result_status = result.get(
                    "status"
                )

                # =================================================
                # REFUSED QUESTION
                # =================================================

                if result_status == "refused":

                    st.warning(
                        "🚫 Question cannot be answered"
                    )

                    st.write(
                        result.get(
                            "answer",
                            (
                                "The question cannot be "
                                "answered from the available data."
                            ),
                        )
                    )

                    # ---------------------------------------------
                    # Refusal plan
                    # ---------------------------------------------

                    plan = result.get(
                        "plan"
                    )

                    if plan:

                        with st.expander(
                            "View refusal details"
                        ):

                            st.json(
                                plan
                            )

                # =================================================
                # SUCCESSFUL QUESTION
                # =================================================

                else:

                    # ---------------------------------------------
                    # Answer
                    # ---------------------------------------------

                    st.subheader(
                        "Answer"
                    )

                    answer = result.get(
                        "answer",
                        "No answer returned.",
                    )

                    st.success(
                        answer
                    )

                    # ---------------------------------------------
                    # Results
                    # ---------------------------------------------

                    query_result = result.get(
                        "result"
                    )

                    if query_result:

                        rows = query_result.get(
                            "rows",
                            [],
                        )

                        if rows:

                            st.subheader(
                                "Results"
                            )

                            st.dataframe(
                                rows,
                                use_container_width=True,
                                hide_index=True,
                            )

                        else:

                            st.info(
                                "The query returned no rows."
                            )

                    # ---------------------------------------------
                    # SQL
                    # ---------------------------------------------

                    generated_sql = result.get(
                        "sql"
                    )

                    if generated_sql:

                        with st.expander(
                            "View generated SQL"
                        ):

                            st.code(
                                generated_sql,
                                language="sql",
                            )

                    # ---------------------------------------------
                    # Query plan
                    # ---------------------------------------------

                    plan = result.get(
                        "plan"
                    )

                    if plan:

                        with st.expander(
                            "View query plan"
                        ):

                            st.json(
                                plan
                            )

                    # ---------------------------------------------
                    # Job information
                    # ---------------------------------------------

                    with st.expander(
                        "View job details"
                    ):

                        st.write(
                            f"**Job ID:** `{question_job_id}`"
                        )

                        st.write(
                            "**Status:** completed"
                        )

        except requests.exceptions.ConnectionError:

            st.error(
                "Could not connect to the FastAPI server. "
                "Make sure FastAPI is running on "
                "http://127.0.0.1:8000."
            )

        except requests.exceptions.Timeout:

            st.error(
                "The request timed out. "
                "Please check that the API server is running."
            )

        except Exception as exc:

            st.error(
                f"Error: {exc}"
            )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Natural Language Insights • "
    "FastAPI + DuckDB + Gemini"
)
