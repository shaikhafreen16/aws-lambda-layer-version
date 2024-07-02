import boto3

def get_latest_layer_version(client, layer_name):
    try:
        response = client.list_layer_versions(LayerName=layer_name, MaxItems=1)
        if response['LayerVersions']:
            return response['LayerVersions'][0]['Version']
        else:
            return None
    except client.exceptions.ResourceNotFoundException:
        return None

def create_or_update_layer(client, layer_name, version, zip_file):
    existing_version = get_latest_layer_version(client, layer_name)
    
    if existing_version == version:
        print(f"Layer {layer_name} already exists with version {version}. No update needed.")
        return existing_version
    elif existing_version:
        print(f"Layer {layer_name} exists with version {existing_version}. Updating to version {version}.")
    else:
        print(f"Layer {layer_name} does not exist. Creating new layer with version {version}.")
    
    with open(zip_file, 'rb') as f:
        response = client.publish_layer_version(
            LayerName=layer_name,
            Content={'ZipFile': f.read()},
            CompatibleRuntimes=['python3.7', 'python3.8', 'python3.9', 'python3.10'],  # adjust as necessary
            CompatibleArchitectures=['x86_64', 'arm64'],
            Description=f"Version {version} of {layer_name}"
        )
    
    new_version = response['Version']
    print(f"New layer version published: {new_version}")
    return new_version

def update_lambda_functions(client, layer_name, version):
    functions = client.list_functions()['Functions']
    
    for function in functions:
        function_name = function['FunctionName']
        response = client.get_function_configuration(FunctionName=function_name)
        layers = response.get('Layers', [])
        layer_arn = None
        for layer in layers:
            if layer_name in layer['Arn']:
                layer_arn = layer['Arn']
                break
        
        if layer_arn:
            current_version = int(layer_arn.rsplit(':', 1)[1])
            if current_version == version:
                print(f"Function {function_name}: Layer {layer_name} already at version {version}. No update needed.")
            else:
                new_layer_arn = layer_arn.rsplit(':', 1)[0] + f":{version}"
                layers = [layer for layer in layers if layer['Arn'] != layer_arn]
                layers.append({'Arn': new_layer_arn})
                print(f"Function {function_name}: Layer {layer_name} updated from version {current_version} to version {version}")
                client.update_function_configuration(
                    FunctionName=function_name,
                    Layers=[layer['Arn'] for layer in layers]
                )
                print(f"Function {function_name} configuration updated with layer {layer_name} version {version}")
        else:
            response = client.list_layer_versions(LayerName=layer_name)
            layer_arn = response['LayerVersions'][0]['LayerVersionArn']
            layers.append({'Arn': layer_arn})
            print(f"Function {function_name}: Layer {layer_name} added with version {version}")
            client.update_function_configuration(
                FunctionName=function_name,
                Layers=[layer['Arn'] for layer in layers]
            )
            print(f"Function {function_name} configuration updated with layer {layer_name} version {version}")

def update_lambda_layers(layers_info):
    client = boto3.client('lambda')
    
    for layer_name, layer_info in layers_info.items():
        new_version = create_or_update_layer(
            client,
            layer_name,
            layer_info['version'],
            layer_info['zip_file']  # Use directly uploaded zip file path
        )
        update_lambda_functions(client, layer_name, new_version)

# Example usage
layers_info = {
    'your-layer-name': {
        'version': 'your version for the layer',
        'zip_file': 'path/to/your/db-connection-layer.zip'
    }
}

update_lambda_layers(layers_info)