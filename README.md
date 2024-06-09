# socketProgramming
### server
- Able to send command to the client via Rest API
- Get history of client responses received by the server
### client 
- real time streaming out command output received from the server


#### Register curl

$headers = @{}
$headers["Content-Type"] = "application/json"

$body = @{
    client_id = "client_1234"
} | ConvertTo-Json

Invoke-WebRequest -Uri http://127.0.0.1:5000/register -Method Post -Headers $headers -Body $body


#### Send command 
# Define the URL
$uri = "http://127.0.0.1:5000/send-command"
$headers = @{
    "Content-Type" = "application/json"
}
$body = @{
    "command" = "ipconfig"  # Example command
    "client_id" = "client_1234"  # Example client ID
} | ConvertTo-Json

Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $body