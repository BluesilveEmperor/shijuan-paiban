# DOCX -> PDF via Word COM, into the OCR staging dir
$ErrorActionPreference = 'Stop'
$pairs = @(
  @{ src = 'D:\Music\试题加题库\高三数学\河南省2025年高考综合改革适应性演练 -解析.docx'
     dst = 'C:\Users\HW\AppData\Local\Temp\deveco\shijuan-stage\河南省2025年高考综合改革适应性演练-数学参考答案.pdf' },
  @{ src = 'D:\Music\试题加题库\高三数学\数学思考2025年03月资料分享\山东省烟台市、德州、东营市2025届高三一模数学试题\山东省烟台市2024-2025学年高三一模数学试题.docx'
     dst = 'C:\Users\HW\AppData\Local\Temp\deveco\shijuan-stage\山东省烟台市2024-2025学年高三一模数学试题.pdf' },
  @{ src = 'D:\Music\试题加题库\高三数学\数学思考2025年03月资料分享\浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题\浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题.docx'
     dst = 'C:\Users\HW\AppData\Local\Temp\deveco\shijuan-stage\浙江省杭州学军中学2024-2025学年高三下学期3月月考数学试题.pdf' }
)
New-Item -ItemType Directory -Force -Path 'C:\Users\HW\AppData\Local\Temp\deveco\shijuan-stage' | Out-Null
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
  foreach ($p in $pairs) {
    Write-Output ("converting: " + (Split-Path $p.src -Leaf))
    $doc = $word.Documents.Open($p.src, $false, $true)
    $doc.SaveAs2($p.dst, 17)  # wdFormatPDF
    $doc.Close($false)
    Write-Output ("  -> " + $p.dst)
  }
} finally {
  $word.Quit()
}
Write-Output 'ALL DOCX CONVERTED'
