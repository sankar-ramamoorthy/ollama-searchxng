import gradio as gr
import requests

BACKEND_URL = "http://backend_svc:8000/chat"  # Adjust as needed

def chat_with_backend(message, history):
    debug_logs = []
    debug_logs.append(f"Sending message to backend: {message}")
    data = {"message": message, "history": history}
    try:
        response = requests.post(BACKEND_URL, json=data)
        response.raise_for_status()
        backend_resp = response.json().get("response", "No response")
        debug_logs.append(f"Received backend response: {backend_resp}")
    except Exception as e:
        backend_resp = f"Error: {str(e)}"
        debug_logs.append(f"Error calling backend: {str(e)}")

    history = history + [(message, backend_resp)]
    debug_log_text = "\n".join(debug_logs)
    return history, history, debug_log_text


with gr.Blocks() as demo:
    chatbot = gr.Chatbot()
    msg = gr.Textbox(placeholder="Type your message here")
    state = gr.State([])
    debug_output = gr.Textbox(label="Debug Log", interactive=False, lines=10)

    # Inputs: message textbox, chat history
    # Outputs: chatbot messages, updated history state, debug log textbox
    msg.submit(chat_with_backend, inputs=[msg, state], outputs=[chatbot, state, debug_output])
    msg.submit(lambda: "", [], msg)  # Clear input box after submit

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
