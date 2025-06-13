import os

from bs4 import BeautifulSoup

fail_json = {}
log_dir = "logs/containerized-tests/"
xml_files = [filename for filename in os.listdir(log_dir) if filename.endswith(".xml")]
failures = 0
errors = 0

for xml_file in xml_files:
    file_path = os.path.join(log_dir, xml_file)
    with open(file_path, encoding="utf-8") as file_read:
        soup = BeautifulSoup(file_read, "xml")

        testsuite = soup.find("testsuite")
        failures = failures + int(testsuite["failures"])
        errors = errors + int(testsuite["errors"])

        testcases = soup.find_all("testcase")
        for testcase in testcases:
            class_name = testcase["classname"]
            name = testcase["name"]
            failure = testcase.find("failure")

            if failure:
                failure_message = failure["message"]
                if f"{name} in Class: {class_name}" not in fail_json:
                    fail_json[f"{name} in Class: {class_name}"] = {}
                if failure_message not in fail_json[f"{name} in Class: {class_name}"]:
                    fail_json[f"{name} in Class: {class_name}"][failure_message] = []
                fail_json[f"{name} in Class: {class_name}"][failure_message].append(
                    xml_file
                )


def sorting_key(list_of_test: str) -> int:
    return sum(len(files) for files in fail_json[list_of_test].values())


# Sort the test cases based on the total length of failure message count
sorted_test_cases = sorted(fail_json.keys(), key=sorting_key, reverse=True)

# Create a new dictionary with sorted test cases
sorted_data = {test_fail: fail_json[test_fail] for test_fail in sorted_test_cases}


with open(log_dir + "summary.txt", "w", encoding="utf-8") as file_write:
    file_write.write("Summary: \n")
    file_write.write(f"\tFailures = {failures} \n")
    file_write.write(f"\tErrors = {errors} \n")
    file_write.write(f"\tIn {len(xml_files)} testing iterations \n")
    file_write.write("-" * 50 + "\n")

    for test_case, failure_messages in sorted_data.items():
        file_write.write(f"Test Case: {test_case}\n")
        for failure_message, file_locations in failure_messages.items():
            file_write.write(f"\t Failure Message: {failure_message}\n")
            file_write.write(f"\t Count: {len(file_locations)}\n")
            file_write.write("\t File:\n")
            for file_location in file_locations:
                file_write.write(f"\t\t - {file_location}\n")
        file_write.write("-" * 50 + "\n")
