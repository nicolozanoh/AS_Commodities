from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyCYJZY_LNEFyUU7p_r8kSG5A1l48Mp4Hh4")

# Iterate through your recent jobs
for batch_job in client.batches.list():
    if batch_job.state == types.JobState.JOB_STATE_PENDING:
        print(f"Name: {batch_job.name}")
        print(f"Display Name: {batch_job.display_name}")
        print(f"State: {batch_job.state}")
        print(f"Created: {batch_job.create_time}")
        print("-" * 20)

        client.batches.cancel(name=batch_job.name)