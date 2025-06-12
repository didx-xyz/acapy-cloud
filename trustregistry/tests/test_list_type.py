from trustregistry.list_type import StringList


def test_process_bind_param():
    # Test the process_bind_param method of StringList
    string_list_type = StringList()
    result = string_list_type.process_bind_param(["value1", "value2"], None)
    assert result == "value1,value2"


def test_process_result_value():
    # Test the process_result_value method of StringList
    string_list_type = StringList()
    result = string_list_type.process_result_value("value1,value2", None)
    assert result == ["value1", "value2"]


def test_process_result_value_not_list():
    # Test the process_result_value method of StringList with None value
    string_list_type = StringList()
    result = string_list_type.process_bind_param("word", None)
    assert result == "word"
