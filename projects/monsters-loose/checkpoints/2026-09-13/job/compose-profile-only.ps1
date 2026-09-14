param([string]$Generated)
Add-Type -AssemblyName System.Drawing
$assetDir = Join-Path $PSScriptRoot 'assets'
$original = [System.Drawing.Bitmap]::new((Join-Path $assetDir 'CHAR-001-CU-v001.png'))
$revision = [System.Drawing.Bitmap]::new($Generated)
$result = $original.Clone()
$graphics = [System.Drawing.Graphics]::FromImage($result)
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
# Keep the original grid and every pixel outside the interior of panel B.
$x = [int]($original.Width / 2) + 2
$y = 2
$w = $original.Width - $x - 2
$h = [int]($original.Height / 2) - 4
$dest = [System.Drawing.Rectangle]::new($x,$y,$w,$h)
$sx = [single]($x * $revision.Width / $original.Width)
$sy = [single]($y * $revision.Height / $original.Height)
$sw = [single]($w * $revision.Width / $original.Width)
$sh = [single]($h * $revision.Height / $original.Height)
$graphics.DrawImage($revision,$dest,$sx,$sy,$sw,$sh,[System.Drawing.GraphicsUnit]::Pixel)
$graphics.Dispose()
$output = Join-Path $assetDir 'CHAR-001-CU-v002-composite.png'
$result.Save($output,[System.Drawing.Imaging.ImageFormat]::Png)
$reloaded = [System.Drawing.Bitmap]::new($output)
$changedOutside = 0
for ($py=0; $py -lt $original.Height; $py++) {
  for ($px=0; $px -lt $original.Width; $px++) {
    if ($px -ge $x -and $px -lt ($x+$w) -and $py -ge $y -and $py -lt ($y+$h)) { continue }
    if ($original.GetPixel($px,$py).ToArgb() -ne $reloaded.GetPixel($px,$py).ToArgb()) { $changedOutside++ }
  }
}
$original.Dispose(); $revision.Dispose(); $result.Dispose(); $reloaded.Dispose()
if ($changedOutside -ne 0) { throw "Changed $changedOutside pixels outside B" }
@{image=$output;changed_pixels_outside_B=$changedOutside} | ConvertTo-Json
