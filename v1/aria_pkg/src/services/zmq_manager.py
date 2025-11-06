import json
from typing import Dict
import zmq

ZMQ_COMMAND_PORT = 5556
ZMQ_AVALON_PORT = 8000
ZMQ_LLM_PUB_PORT = 5557


class ZMQManager:
    """Manages ZeroMQ socket connections."""

    def __init__(self):
        self.context = zmq.Context()
        self.command_socket = None
        self.avalon_socket = None
        self.llm_pub_socket = None

    def setup_sockets(self):
        """Initialize and configure all ZMQ sockets."""
        # Command publisher
        self.command_socket = self.context.socket(zmq.PUB)
        self.command_socket.bind(f"tcp://*:{ZMQ_COMMAND_PORT}")
        print(f"ZMQ bound to port {ZMQ_COMMAND_PORT}: publishing commands")

        # Avalon request socket
        self.avalon_socket = self.context.socket(zmq.REQ)
        # SSH -L tunnel <local_port>:<remote_ip>:<remote_port>
        self.avalon_socket.connect(f"tcp://localhost:{ZMQ_AVALON_PORT}")
        print("ZMQ connected to Avalon1: Requesting GPT inference")

        # LLM publisher
        self.llm_pub_socket = self.context.socket(zmq.PUSH)
        self.llm_pub_socket.connect(f"tcp://localhost:{ZMQ_LLM_PUB_PORT}")
        print(f"ZMQ connected to port {ZMQ_LLM_PUB_PORT}: pushing GPT inference result")

    def send_command(self, command: str):
        """Send command via command socket."""
        if self.command_socket:
            self.command_socket.send_string(f"command {command}")

    def request_gpt_inference(self, question: str) -> Dict:
        """Send question to Avalon and wait for response."""
        if not self.avalon_socket:
            raise RuntimeError("Avalon socket not initialized")

        self.avalon_socket.send_string(question)
        print("Starting GPT inference: Question sent to Avalon1 server...")
        return self.avalon_socket.recv_json()

    def publish_tool_call(self, tool_response: Dict):
        """Publish tool call to LLM socket."""
        if self.llm_pub_socket:
            tool_string = json.dumps(tool_response, indent=2)
            self.llm_pub_socket.send_string(tool_string)
            print(f"Tool call published to PandaPC:\n{tool_string}")

    def close_all(self):
        """Close all sockets."""
        for socket in [self.command_socket, self.avalon_socket, self.llm_pub_socket]:
            if socket:
                socket.close()
