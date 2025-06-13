from pydantic import ValidationError


def extract_validation_error_msg(e: ValidationError) -> str:
    output = ""
    for error in e.errors():
        loc = error.get("loc") or ["Error:"]
        field = loc[0]  # Gets the problematic field, or default string "Error:"
        msg = error["msg"]  # msg is prefaced with: "Value error, <what we want>"
        msg_without_value_error = msg.split(", ", maxsplit=1)[1] if ", " in msg else msg
        output += f"{field} {msg_without_value_error}\n"
    return output.strip()
