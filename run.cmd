
# to run: $ bash run.cmd

target="participants_123456789.csv"
utility="zoompart.py"
$utility \
  --verbose \
  --dat-file \
  --nominal-duration=130 \
  --cutoff=20 \
  --title="Test plot" \
  $target
