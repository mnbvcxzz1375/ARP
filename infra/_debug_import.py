import traceback; import sys; sys.path.insert(0, "/app"); exec("try:
    from app.main import app
    print(type(app))
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
")