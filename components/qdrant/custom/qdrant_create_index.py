from langflow.base.flow_processing.utils import build_repr
from langflow.base.io.text import TextComponent
from langflow.io import StrInput, SecretStrInput, IntInput
from langflow.schema.data import Data

class QdrantCreateIndex(TextComponent):
    display_name = "Qdrant Create Payload Index"
    description = "Creates a payload index on a Qdrant collection's field."
    icon = "Qdrant"

    inputs = [
        StrInput(name="host", display_name="Host", value="localhost", advanced=True),
        IntInput(name="port", display_name="Port", value=6333, advanced=True),
        SecretStrInput(name="api_key", display_name="Qdrant API Key", advanced=True),
        StrInput(name="collection_name", display_name="Collection Name", required=True),
        StrInput(name="field_name", display_name="Field Name", required=True, info="The name of the payload field to index."),
    ]

    def build(self) -\u003e Data:
        try:
            from qdrant_client import QdrantClient, models

            client = QdrantClient(host=self.host, port=self.port, api_key=self.api_key)

            client.create_payload_index(
                collection_name=self.collection_name,
                field_name=self.field_name,
                field_schema=models.TextIndexParams(
                    type="text",
                    tokenizer=models.TokenizerType.MULTILINGUAL,
                    min_token_len=2,
                    lowercase=True,
                ),
            )
            result_text = f"Successfully created payload index for field '{self.field_name}' in collection '{self.collection_name}'."
            self.status = result_text
        except Exception as e:
            result_text = f"Failed to create payload index. Error: {e}"
            self.status = result_text

        return Data(data=result_text)