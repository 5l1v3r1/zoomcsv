
# to run: $ bash run.cmd

target="participants_123456789.csv"
utility="zoompart.py"

case "$1" in
    --help|--hel|--he|--h|-help|-hel|-he|-h|"-?")
        shift
        echo "   usage: run without options or arguments"
        echo " purpose: issue a test command for $utility"
        exit 0
        ;;
esac

$utility \
  --verbose \
  --dat-file \
  --nominal-duration=130 \
  --cutoff=20 \
  --title="Test plot" \
  $target

# end of file
