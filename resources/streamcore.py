import os
import oci
import shortuuid
import uuid
import streamlit as st
from streamlit_feedback import streamlit_feedback
from resources.utils import (return_keys_from_endpoint_config,
                             fetch_endpoint_ocid,
                             set_region)

class Agent:
    def __init__(self, logger):
        self.CONFIG_PROFILE = os.getenv("oci_config_profile", default="DEFAULT")
        self.oci_config = oci.config.from_file(profile_name=self.CONFIG_PROFILE)
        self.logger = logger


    def init_chat_history(self):
        self.logger.info("Initiating chat ui")
        st.session_state["session_uuid"] = f"{str(uuid.uuid4())}"
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "session_id" not in st.session_state:
            st.session_state.session_id = None
            self.logger.info("Invalidating session ID")

    def create_oci_client(self, region):
        try:
            generative_ai_agent_runtime_client = oci.generative_ai_agent_runtime.GenerativeAiAgentRuntimeClient(
                config=self.oci_config,
                service_endpoint=os.environ['oci_agent_base_url'],
                region=region)
            self.logger.info("Starting new OCI client")
            return generative_ai_agent_runtime_client
        except Exception as error:
            self.logger.DEBUG(f"Failed to invoke client generation {error}")


    @staticmethod
    def sidebar_message():
        st.sidebar.markdown(
            """
            ### About.
            A simple UI to call [OCI Genai Agent endpoints](https://docs.oracle.com/en-us/iaas/Content/generative-ai-agents/home.htm)
            ### Credits.
            - **Creator - rahul.m.r@oracle.com**.
            
            """
        )

    def session_exit(self, agent_oci_client):
        try:
            if st.session_state.session_id is not None:
                agent_endpoint = os.environ['agent_endpoint']
                self.logger.info("Attempting session exit")
                delete_session_response = agent_oci_client.delete_session(
                    agent_endpoint_id = agent_endpoint,
                    session_id = st.session_state.session_id)
                self.logger.info(f"Logout done - {str(delete_session_response.data)}/{str(delete_session_response.status)}")
        except Exception as error:
            self.logger.error(f"Logout failed - {error}")


    def logout(self,agent_oci_client):
        col1, col2, col3 = st.columns([2,2,2])
        with col2:
            if st.button("【⏻]", use_container_width=False, help="Logout Chat Session"):
                self.logger.info("Attempting chat session deletion")
                self.session_exit(agent_oci_client)

    def sidebar(self):
        agent_endpoint = os.environ['agent_endpoint']
        region = set_region(agent_endpoint)
        agent_oci_client = self.create_oci_client(region)
        with st.sidebar:
            list_of_keys = return_keys_from_endpoint_config()
            selection = st.sidebar.selectbox("Select Endpoint", list_of_keys)
            self.logger.info("Got list of keys")
            if selection == "Custom":
                agent_endpoint = st.text_input("Enter an Agent OCID",value="")
            else:
                agent_endpoint = fetch_endpoint_ocid(selection)
            os.environ['agent_endpoint'] = agent_endpoint
            self.logger.info(f"Loading with endpoint {os.environ['agent_endpoint']}")
            col1, col2, col3 = st.columns([1,1,1])
            with col1:
                if st.button("🔄", type="secondary", use_container_width=True, help="Reset chat history/Update Endpoint"):
                    st.session_state.messages = []
                    st.session_state.session_id = None
                    self.logger.info("Reloading the chat.")
                    self.session_exit(agent_oci_client)
                    st.rerun()
            with col2:
                data = str(st.session_state)
                filename =  f"session_histroy_{shortuuid.ShortUUID().random(length=6)}.txt"
                if st.download_button("⬇️", data, filename, use_container_width=True, help="Download Chat histroy with feedback"):
                    self.logger.info(f"Downloaded chat history {filename}")

            self.sidebar_message()
            self.logout(agent_oci_client)
            self.agent_footer()

    def warning_message(self, message):
        self.logger.info(f"Warning message invoked - {message}")
        st.warning(message, icon="⚠️")

    def agent_feedback(self):
        st.toast("Feedback saved.",icon="✔️")
        self.logger.info(f"Feedback received for f{st.session_state.session_id}")

    @staticmethod
    def agent_footer():
        footer = """<style>.footer {position: fixed;left: 0;bottom: 0;width: 100%;
                 background-color: #F0F0F0;color: black;text-align: center;}
                </style><div class='footer'><p> 🏷️ 0.1.0b | 🅾️ Powered by OCI Generative AI Agent | ©️ - Oracle 2024  </p></div>"""
        st.markdown(footer, unsafe_allow_html=True)

    def agent_load(self, display_name, description, stream_option):
        agent_endpoint = os.environ['agent_endpoint']
        self.logger.info(f"Loading agent with {os.environ['agent_endpoint']}")
        region = set_region(agent_endpoint)
        self.logger.info(f"Using oci region {region}")
        st.info(f"🔍 Agent {agent_endpoint} joined the Chat ..")
        self.sidebar()
        if st.session_state.session_id is None:
            agent_oci_client = self.create_oci_client(region)
            try:
                create_session_response = agent_oci_client.create_session(
                    create_session_details=oci.generative_ai_agent_runtime.models.CreateSessionDetails(
                    display_name=display_name,
                    description=description),
                    agent_endpoint_id=agent_endpoint)
                st.session_state.session_id = create_session_response.data.id
                if hasattr(create_session_response.data, 'welcome_message'):
                    st.session_state.messages.append({"role": "assistant", "content": create_session_response.data.welcome_message})
            except Exception as error:
                self.logger.error(f"Failed to create session {error}")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        # Get user input
        if user_input := st.chat_input("How can I help you .. "):
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user", avatar="💬"):
                st.markdown(user_input)
            with st.spinner():
                self.logger.info("Attempting execution ..")
                agent_oci_client = self.create_oci_client(region)
                chat_response = agent_oci_client.chat(
                    agent_endpoint_id=agent_endpoint,
                    chat_details=oci.generative_ai_agent_runtime.models.ChatDetails(
                        user_message=f"{str(user_input)}.Always share all possible hyper links if found any in the output",
                        should_stream=False,
                        session_id=st.session_state.session_id),
                )

            if chat_response.status == 200:
                self.logger.info(f"Received API output with return as 200")
                response_content = chat_response.data.message.content
                st.session_state.messages.append({"role": "assistant", "content": response_content.text})
                with st.chat_message("assistant"):
                    st.markdown(response_content.text)
                if response_content.citations:
                    with st.expander("Citations"):
                        for i, citation in enumerate(response_content.citations, start=1):
                            st.write(f"**Citation {i}:**")  # Add citation number
                            st.markdown(f"**Source:** [{citation.source_location.url}]({citation.source_location.url})")
                            st.text_area("Citation Text", value=citation.source_text, height=200)
                with st.form('form'):
                    streamlit_feedback(feedback_type="thumbs",
                                       optional_text_label="[Optional] Please provide an explanation",
                                       align="flex-start",
                                       key='fb_k')
                    st.form_submit_button('Save feedback', on_click=self.agent_feedback)
            else:
                self.logger.error(f"API execution failed with error {chat_response.status}")
