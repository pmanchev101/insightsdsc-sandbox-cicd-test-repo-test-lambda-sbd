import argparse
import os
import yaml

DEFAULT_LAMBDA_PYTHON_CODE = """
def lambda_handler(event, context):
    return {
        'message': event
    }
"""

configs = {
    "lambda_folder": "lambdas"
}


def create_lambda_function(name, cwd):
    yml_adjusted_name = "".join(name.replace("-", " ").title().split(" "))
    lambda_files = ["lambda.yml", "lambda_policy.yml", "lambda_role.yml", "params.yml"]
    lambda_variables = {
        "<<!lambda_folder!>>": configs['lambda_folder'],
        "<<!lambda_name!>>": name,
        "<<!lambda_yml_name!>>": yml_adjusted_name
    }

    new_lambda_path = os.path.join(os.path.dirname(cwd), configs['lambda_folder'], name)
    serverless_path = os.path.join(new_lambda_path, "serverless")

    os.mkdir(new_lambda_path)
    os.mkdir(serverless_path)

    # create serverless provisioning files
    for file_name in lambda_files:
        file = open(os.path.join(cwd, "modules", "lambda", file_name), "r")
        lambda_yml = file.readlines()
        lambda_yml = "".join(lambda_yml)

        for key, value in lambda_variables.items():
            lambda_yml = lambda_yml.replace(key, value)

        file = open(os.path.join(serverless_path, file_name), "x")
        file.write(lambda_yml)
        file.close()

    # create default lambda handler
    file = open(os.path.join(new_lambda_path, "handler.py"), "x")
    file.write(DEFAULT_LAMBDA_PYTHON_CODE)
    file.close()

    # modify serverless.yml to include new function
    with open(os.path.join(os.path.dirname(cwd), "serverless.yml"), "r") as stream:
        try:
            serverless = yaml.safe_load(stream)
            serverless['functions'].append("${file(./" + configs['lambda_folder'] + "/"
                                           + name + "/serverless/lambda.yml)}")
            serverless['resources'].append("${file(./" + configs['lambda_folder'] + "/"
                                           + name + "/serverless/lambda_role.yml)}")

            with open(os.path.join(os.path.dirname(cwd), "serverless.yml"), "w") as output:
                yaml.dump(serverless, output, default_flow_style=False)
        except yaml.YAMLError as exc:
            print(exc)


resource_mapping = {
    "lambda_function": create_lambda_function
}


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generates serverless provisioning files and modifies existing serverless.yml to add necessary code"
    )
    parser.add_argument("-n", "--name")
    parser.add_argument("--lambda_function", action="store_const", const="lambda_function")
    parser.add_argument("--glue_job", action="store_const", const="glue_job")
    return parser


def main() -> None:
    parser = init_argparse()
    args = parser.parse_args()
    cwd = os.path.dirname(os.path.realpath(__file__))

    resources = [getattr(args, arg) if arg != "name" else None for arg in vars(args)]
    resources = list(filter(lambda x: x, resources))

    # validation resource choice
    if len(resources) == 0:
        print("No resource selected")
        exit(1)

    if len(resources) > 1:
        print("Please select one resource to provision at a time")
        exit(1)

    # validate name selection
    if not args.name:
        print("No resource name specified")
        exit(1)
    resource = resources[0]

    resource_mapping[resource](args.name, cwd)


main()
