"""Report API — download the self-contained HTML progress report (F5, T5.1).

One endpoint: GET /report?weeks=N. It REUSES the other routers' functions
(trends, days, goals) as plain Python calls — same numbers as the app shows,
computed once, no duplicated SQL — and hands them to the report builder.

The response is served as a download (Content-Disposition: attachment), so
the browser saves a .html file the user can keep, email, or open offline.
"""

from datetime import date, datetime

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.routers.days import day_summaries
from app.routers.goals import active_goal
from app.routers.trends import trends as get_trends
from app.services.report import build_report_html

router = APIRouter(prefix="/report", tags=["report"])


@router.get("", response_class=HTMLResponse)
def download_report(weeks: int = 8) -> HTMLResponse:
    """Generate and download the progress report for the last `weeks` weeks.

    Returns a complete HTML document with Content-Disposition: attachment,
    which makes browsers save it as a file instead of navigating to it.
    """
    # One trends call gives us the weekly buckets AND the weight series,
    # and fixes the period (its first bucket's Monday) for everything else.
    t = get_trends(weeks)
    start = t.weeks[0].week_start
    end = date.today().isoformat()

    # Same day summaries the History screen shows — each day already paired
    # with the goal that was active ON that day (the versioning rule).
    days = day_summaries(start=start, end=end)

    # Today's goal, for the target line on the intake chart.
    goal = active_goal(end)

    # Dates in the label wear the app-wide display format (D5).
    fmt = lambda iso: datetime.fromisoformat(iso).strftime("%d-%b-%Y")
    html_doc = build_report_html(
        period_label=f"Last {weeks} weeks ({fmt(start)} to {fmt(end)})",
        weeks=t.weeks,
        weights=t.weights,
        days=days,
        goal_calories=goal.calories_target if goal else None,
    )
    return HTMLResponse(
        content=html_doc,
        headers={
            # "attachment" = save as file; filename includes the date so
            # multiple exports don't overwrite each other.
            "Content-Disposition": f'attachment; filename="progress-report-{end}.html"'
        },
    )
