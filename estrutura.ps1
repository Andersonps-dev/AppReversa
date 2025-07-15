param (
    [string]$Path = ".",
    [int]$Level = 0,
    [string[]]$IgnorarPastas = @("node_modules", ".git", "dist", "build")
)

function Mostrar-Arvore {
    param (
        [string]$CurrentPath,
        [int]$Level,
        [string[]]$IgnorarPastas
    )

    $nome = Split-Path $CurrentPath -Leaf
    if ($IgnorarPastas -contains $nome) {
        return
    }

    $prefixo = (" " * ($Level * 4)) + "- "

    if (Test-Path $CurrentPath -PathType Container) {
        Write-Host "$prefixo$nome/"
        $itens = Get-ChildItem -LiteralPath $CurrentPath -Force | Sort-Object { !$_.PSIsContainer }, Name
        foreach ($item in $itens) {
            Mostrar-Arvore -CurrentPath $item.FullName -Level ($Level + 1) -IgnorarPastas $IgnorarPastas
        }
    } else {
        Write-Host "$prefixo$nome"
    }
}

$fullPath = Resolve-Path $Path
Mostrar-Arvore -CurrentPath $fullPath -Level 0 -IgnorarPastas $IgnorarPastas
