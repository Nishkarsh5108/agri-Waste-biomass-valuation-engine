from supabase import create_client, Client
from app.core.config import settings

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def upload_image(file_bytes: bytes, filename: str) -> str:
    """
    Uploads a file to the 'biomass-photos' bucket and returns its public URL.
    Ensure the 'biomass-photos' bucket exists and is public in the Supabase Dashboard.
    """
    bucket_name = "biomass-photos"
    try:
        # Note: the python supabase client takes (path, file)
        res = supabase.storage.from_(bucket_name).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": "image/jpeg"}
        )
    except Exception as e:
        # If it fails, maybe it already exists or bucket is missing. We raise it for debugging.
        raise e
        
    public_url = supabase.storage.from_(bucket_name).get_public_url(filename)
    return public_url
