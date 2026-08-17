# Permanent startup script for LiteLLM gateway (s9 assignment)
# Loads only the required Azure OpenAI credentials from root .env
# Uses $PSScriptRoot to resolve the .env path dynamically (2 levels up from this script)
# Clears DATABASE_URL in this process to prevent LiteLLM from attempting Prisma/DB connection

$rootEnvPath = (Get-Item $PSScriptRoot).Parent.Parent.FullName + "\.env"

if (Test-Path $rootEnvPath) {
    # Load only the 4 Azure variables needed by LiteLLM
    $envVars = Get-Content $rootEnvPath | Where-Object { $_ -match '^(AZURE_OPENAI_API_KEY|AZURE_OPENAI_ENDPOINT|AZURE_OPENAI_API_VERSION|AZURE_OPENAI_LLM_DEPLOYMENT)=' }
    $envVars | ForEach-Object {
        $key, $value = $_ -split '=', 2
        [System.Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), "Process")
    }
} else {
    Write-Host "Warning: Root .env not found at $rootEnvPath — Azure credentials may be missing."
}

# Unset DATABASE_URL for this process only — does NOT affect system or other terminals
[System.Environment]::SetEnvironmentVariable("DATABASE_URL", $null, "Process")

# Start LiteLLM gateway
litellm --config litellm_config.yaml