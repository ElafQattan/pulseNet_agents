set -e
# the dashboard is kept in a private Hugging Face repository; without HF_TOKEN only the API runs
if [ -n "$HF_TOKEN" ]; then
  uv run python -c "
import os
from huggingface_hub import snapshot_download
snapshot_download('Elafqattan/pulsenet-dashboard', repo_type='dataset', local_dir='pulsenet/ui',
                  token=os.environ['HF_TOKEN'], allow_patterns=['*.html', '*.css', '*.js'])
"
fi
exec uv run pulsenet/api.py --host 0.0.0.0
