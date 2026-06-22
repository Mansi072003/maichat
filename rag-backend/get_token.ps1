$apiKey = "AIzaSyBhgeYrtSHPo_sJmUDWqTcE_aI6d3Exqok"
$email  = "test@example.com"
$pass   = "123456789"

$body = @{ email = $email; password = $pass; returnSecureToken = $true } | ConvertTo-Json
$url  = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$apiKey"

$resp = Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
$resp.idToken