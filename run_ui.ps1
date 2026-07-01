param(
    [int[]]$PreferredPorts = @(8501, 8502, 8503)
)

function Test-TcpPortFree {
    param([int]$Port)

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) {
            $listener.Stop()
        }
    }
}

$port = $PreferredPorts | Where-Object { Test-TcpPortFree -Port $_ } | Select-Object -First 1

if (-not $port) {
    throw "No free Streamlit port found in: $($PreferredPorts -join ', ')"
}

Write-Host "Starting Streamlit on http://127.0.0.1:$port"
& .\venv\Scripts\streamlit.exe run ui/app.py --server.port $port --server.headless true
