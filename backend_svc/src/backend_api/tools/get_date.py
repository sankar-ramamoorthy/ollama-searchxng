
def get_date() -> str:
    # Get todays date using python
    from datetime import date,datetime
    today = datetime.now().strftime("%A, %B %d, %Y")
    return f"Here is Todays's date   {str(today)}"
