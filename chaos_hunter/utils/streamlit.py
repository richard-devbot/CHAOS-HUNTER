from typing import List, Dict, Any

import streamlit as st

from .functions import limit_string_length


# stand-alone spiner in streamlit
# ref: https://github.com/streamlit/streamlit/issues/6799
class Spinner:
    def __init__(self, text = "In progress..."):
        self.text = text
        self.empty = st.empty()
        self._spinner = iter(self._start()) # This creates an infinite spinner
        next(self._spinner) #  This starts it
        
    def _start(self):
        with st.spinner(self.text):
            yield
    
    def end(self, text: str = None): # This ends it
        next(self._spinner, None)
        if text is not None:
            self.empty.write(text)


class StreamlitDisplayHandler:
    """Display handler implementation for Streamlit UI"""
    
    def __init__(self, header: str = ""):
        # Create empty containers for dynamic content updates
        st.write(header)
        self.cmd_container = st.empty()
        self.idx = -1
        self.cmd = []
        self.output_text = []

    def on_start(self, cmd: str = ""):
        """Initialize display with progress status"""
        self.cmd.append(limit_string_length(cmd))
        self.output_text.append("")
        self.idx += 1
        output_text = ""
        for i in range(len(self.cmd)):
            if i < len(self.cmd) - 1:
                output_text += f"$ {self.cmd[i]}\n{self.output_text[i]}"
            else:
                output_text += f"$ {self.cmd[i]}"
        self.cmd_container.code(output_text, language="powershell")
        return self.cmd_container

    def on_output(self, output: str):
        """Update output container with new content"""
        if output != "":
            self.output_text[self.idx] += output
            self.output_text[self.idx] = limit_string_length(self.output_text[self.idx])
        output_text = ""
        for i in range(len(self.cmd)):
            output_text += f"$ {self.cmd[i]}\n{self.output_text[i]}"
        self.cmd_container.code(output_text, language="powershell")

    def on_success(self, output: str = ""):
        """Update status to show successful completion"""
        if output != "":
            output_text = ""
            for i in range(self.idx):
                output_text += f"$ {self.cmd[i]}\n{self.output_text[i]}"
            self.output_text[self.idx] = limit_string_length(output)
            output_text += f"$ {self.cmd[self.idx]}\n{self.output_text[self.idx]}"
            self.cmd_container.code(output_text, language="powershell")

    def on_error(self, error: str):
        """Update status and output to show error details"""
        output_text_tmp = f"Error: {error}"
        self.output_text[self.idx] += limit_string_length(output_text_tmp)
        output_text = ""
        for i in range(len(self.cmd)):
            output_text += f"$ {self.cmd[i]}\n{self.output_text[i]}"
        self.cmd_container.code(output_text, language="powershell")


class StreamlitContainer:
    def __init__(
        self,
        text: str = "##### ",
        expanded: bool = True
    ) -> None:
        self.header_empty = st.empty()
        self.header = self.header_empty.expander(text, expanded=expanded)
        self.subcontainers = []
        self.subsubcontainers = []

    def update_header(
        self,
        text: str,
        expanded: bool = True
    ) -> None:
        self.header_empty.expander(text, expanded=expanded)

    def complete_header(self):
        pass

    def create_subcontainer(
        self,
        id: str,
        border: bool = True,
        header: str = ""
    ):
        with self.header:
            subcontainer = st.container(border=border)
            self.subcontainers.append({"id": id, "item": subcontainer})
            if header != "":
                with subcontainer:
                    st.write(header)

    def create_subsubcontainer(
        self,
        subcontainer_id: str,
        subsubcontainer_id: str,
        text: str = None,
        is_code: bool = False,
        language: str = "python"
    ) -> None:
        with self.get_item_from_id(self.subcontainers, subcontainer_id):
            try:
                self.get_item_from_id(self.subsubcontainers, subsubcontainer_id)
                raise RuntimeError(f"The subsub container with id '{subsubcontainer_id}' already exists. No duplicated ids are allowed.")
            except RuntimeError:
                empty = st.empty()
                self.subsubcontainers.append({"id": subsubcontainer_id, "item": empty})
                if text is not None:
                    self.update_subsubcontainer(text, subsubcontainer_id, is_code, language)

    def update_subsubcontainer(
        self,
        text: str,
        id: str,
        is_code: bool = False,
        language: str = "python"
    ) -> None:
        subsubcontainer = self.get_item_from_id(self.subsubcontainers, id)
        if is_code:
            subsubcontainer.code(text, language=language)
        else:
            subsubcontainer.write(text)
    
    def get_item_from_id(
        self,
        data: List[Dict[str, Any]],
        id: str
    ):
        if (item := next((item["item"] for item in data if item["id"] == id), None)) is not None:
            return item
        raise RuntimeError(f"Could not find an sub(sub)container with id '{id}' in the dataset.")

    def get_subcontainer(self, id: str):
        return self.get_item_from_id(self.subcontainers, id)

    def get_subsubcontainer(self, id: str):
        return self.get_item_from_id(self.subsubcontainers, id)