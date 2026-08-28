"""
AI Demand Forecasting Service for Gig Saarthi.

Uses statistical methods (moving average + seasonal weighting) to predict
service demand by category and region. No ML dependencies required.

For production: upgrade to Facebook Prophet or statsmodels Holt-Winters.
"""

import logging
import math
import random
from datetime import timedelta, date
from collections import defaultdict
from django.db.models import Avg, Count, Sum, Q
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


# ── Configuration ──────────────────────────────────────────────────

FORECAST_DAYS = 7  # How many days to forecast
HISTORY_WEEKS = 4  # Weeks of history to use for moving average
SERVICE_CATEGORIES = [
    'cleaning', 'plumbing', 'electrical', 'carpentry',
    'cooking', 'elderly_care', 'gardening', 'painting'
]

# Seasonal multipliers by month (1-12)
# Higher values = higher demand
SEASONAL_WEIGHTS = {
    1: 0.8,   # January — low
    2: 0.8,   # February — low
    3: 0.9,   # March — pre-summer
    4: 1.0,   # April — normal
    5: 1.1,   # May — summer cleaning
    6: 1.2,   # June — monsoon prep
    7: 1.3,   # July — monsoon (plumbing peak)
    8: 1.2,   # August — monsoon
    9: 1.0,   # September — normal
    10: 1.4,  # October — Diwali cleaning peak
    11: 1.3,  # November — post-Diwali
    12: 0.9,  # December — low
}

# Day-of-week weights (0=Monday)
DAY_WEIGHTS = {
    0: 0.9, 1: 0.9, 2: 1.0, 3: 1.0,
    4: 1.1, 5: 1.3, 6: 1.2,  # Weekend peak
}

# Service-specific seasonal patterns
SERVICE_SEASONAL = {
    'cleaning': {10: 1.5, 11: 1.3, 5: 1.2},  # Diwali, summer
    'plumbing': {7: 1.5, 8: 1.4, 6: 1.3},    # Monsoon
    'electrical': {7: 1.2, 10: 1.1},          # Monsoon + Diwali
    'carpentry': {3: 1.2, 4: 1.1, 11: 1.1},  # Pre-summer, post-Diwali
    'cooking': {10: 1.4, 11: 1.3, 7: 1.2},   # Festivals
    'elderly_care': {},                         # Year-round stable
    'gardening': {3: 1.3, 4: 1.2, 9: 1.1},   # Spring
    'painting': {3: 1.3, 4: 1.2, 11: 1.1},   # Pre-summer, post-monsoon
}


# ── Core Forecasting ───────────────────────────────────────────────

def calculate_moving_average(service_category, region='Delhi NCR', weeks=HISTORY_WEEKS):
    """
    Calculate weighted moving average for a service category.
    
    Uses the last N weeks of booking data to compute average daily demand,
    weighted by recency (more recent weeks count more).
    
    Returns: float (average bookings per day)
    """
    from bookings.models import Booking

    now = timezone.now()
    start_date = now - timedelta(weeks=weeks)

    # Count bookings per day of week
    day_counts = defaultdict(list)
    for week_offset in range(weeks):
        week_start = start_date + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=7)

        count = Booking.objects.filter(
            service_category__name__icontains=service_category.replace('_', ' '),
            created_at__gte=week_start,
            created_at__lt=week_end,
        ).count()

        # Weight by recency (newer weeks get higher weight)
        weight = (week_offset + 1) / weeks
        day_counts[week_offset % 7].append(count * weight)

    # Average across all weeks for each day
    if not any(day_counts.values()):
        # No historical data — use a reasonable default
        return 2.0  # Default: ~2 bookings per day

    total_weighted = sum(sum(v) for v in day_counts.values())
    total_days = sum(len(v) for v in day_counts.values() if v)

    if total_days == 0:
        return 2.0

    return total_weighted / total_days


def forecast_demand(service_category, region='Delhi NCR', days=FORECAST_DAYS):
    """
    Generate demand forecast for a service category over N days.
    
    Algorithm:
    1. Calculate moving average from historical data
    2. Apply day-of-week weights
    3. Apply seasonal multipliers
    4. Apply service-specific patterns
    5. Check against available workers
    
    Returns: list of dicts with forecast data
    """
    from workers.models import WorkerProfile

    base_demand = calculate_moving_average(service_category, region)

    # Get available workers for this service
    skill_name = service_category.replace('_', ' ')
    available_workers = WorkerProfile.objects.filter(
        is_verified=True,
        availability_status='available',
        skills__name__icontains=skill_name,
    ).distinct().count()

    forecasts = []
    today = timezone.now().date()

    for day_offset in range(days):
        forecast_date = today + timedelta(days=day_offset)
        day_of_week = forecast_date.weekday()  # 0=Monday
        month = forecast_date.month

        # Apply day-of-week weight
        day_weight = DAY_WEIGHTS.get(day_of_week, 1.0)

        # Apply seasonal weight
        seasonal_weight = SEASONAL_WEIGHTS.get(month, 1.0)

        # Apply service-specific seasonal pattern
        service_weight = SERVICE_SEASONAL.get(service_category, {}).get(month, 1.0)

        # Calculate predicted demand
        predicted = base_demand * day_weight * seasonal_weight * service_weight
        predicted = max(1, round(predicted))  # At least 1

        # Check for shortage
        is_shortage = predicted > available_workers * 1.5  # 1.5x capacity threshold
        recommended = max(1, math.ceil(predicted / 2))  # 2 bookings per worker

        forecasts.append({
            'region': region,
            'service_category': service_category,
            'forecast_date': forecast_date,
            'day_of_week': day_of_week,
            'predicted_demand': predicted,
            'recommended_worker_count': recommended,
            'is_shortage': is_shortage,
            'available_workers': available_workers,
        })

    return forecasts


def generate_all_forecasts(region='Delhi NCR', days=FORECAST_DAYS):
    """
    Generate forecasts for all service categories.
    Returns list of all forecasts.
    """
    all_forecasts = []
    for category in SERVICE_CATEGORIES:
        forecasts = forecast_demand(category, region, days)
        all_forecasts.extend(forecasts)
    return all_forecasts


def save_forecasts(forecasts):
    """
    Save forecast results to the database.
    Updates existing records for the same date+category+region.
    """
    from cooperative_admin.models import DemandForecast

    saved_count = 0
    for f in forecasts:
        forecast, created = DemandForecast.objects.update_or_create(
            region=f['region'],
            service_category=f['service_category'],
            forecast_date=f['forecast_date'],
            defaults={
                'day_of_week': f['day_of_week'],
                'predicted_demand': f['predicted_demand'],
                'recommended_worker_count': f['recommended_worker_count'],
                'is_shortage': f['is_shortage'],
                'model_version': 'v1.0-mavg',
            }
        )
        saved_count += 1

    logger.info(f"Saved {saved_count} forecasts for {forecasts[0]['region'] if forecasts else 'N/A'}")
    return saved_count


# ── Synthetic Data Generation ──────────────────────────────────────

def generate_synthetic_booking_data(region='Delhi NCR', weeks=12):
    """
    Generate synthetic historical booking data for demo purposes.
    Creates bookings with realistic seasonal patterns.
    
    Args:
        region: Region name
        weeks: Number of weeks of history to generate
    """
    from bookings.models import Booking, ServiceCategory, BookingStatusHistory
    from django.contrib.auth import get_user_model

    User = get_user_model()
    customers = list(User.objects.filter(role='customer'))
    if not customers:
        logger.warning("No customers found — cannot generate synthetic data")
        return 0

    categories = list(ServiceCategory.objects.all())
    if not categories:
        logger.warning("No service categories found")
        return 0

    now = timezone.now()
    created_count = 0

    # Map category names to service keys
    category_map = {
        'Home Cleaning': 'cleaning',
        'Plumbing Repair': 'plumbing',
        'Electrical Work': 'electrical',
        'Carpentry & Woodwork': 'carpentry',
        'Cooking & Tiffin': 'cooking',
        'Elderly Care': 'elderly_care',
        'Gardening & Landscaping': 'gardening',
        'Painting Services': 'painting',
    }

    for week_offset in range(weeks, 0, -1):
        week_start = now - timedelta(weeks=week_offset)

        for day in range(7):
            current_date = week_start + timedelta(days=day)
            month = current_date.month
            day_of_week = current_date.weekday()

            for category in categories:
                service_key = category_map.get(category.name, 'cleaning')

                # Base demand with seasonal variation
                base = 2
                seasonal = SEASONAL_WEIGHTS.get(month, 1.0)
                day_w = DAY_WEIGHTS.get(day_of_week, 1.0)
                service_w = SERVICE_SEASONAL.get(service_key, {}).get(month, 1.0)

                daily_demand = max(0, round(base * seasonal * day_w * service_w + random.uniform(-1, 1)))

                for _ in range(daily_demand):
                    # Random time during the day
                    hour = random.randint(8, 18)
                    minute = random.choice([0, 15, 30, 45])
                    scheduled = current_date.replace(hour=hour, minute=minute)

                    # Random location in Delhi NCR
                    lat = 28.6139 + random.uniform(-0.05, 0.05)
                    lng = 77.2090 + random.uniform(-0.05, 0.05)

                    # Most are completed for historical data
                    status = random.choices(
                        ['completed', 'completed', 'completed', 'cancelled_by_customer'],
                        weights=[80, 10, 5, 5]
                    )[0]

                    booking = Booking.objects.create(
                        customer=random.choice(customers),
                        service_category=category,
                        description=f'Synthetic {category.name.lower()} booking',
                        scheduled_datetime=scheduled,
                        is_emergency=random.random() < 0.1,
                        status=status,
                        address_text=f'{random.randint(1, 200)} Synthetic St, {region}',
                        latitude=round(lat, 6),
                        longitude=round(lng, 6),
                        estimated_price=category.base_price,
                        final_price=category.base_price if status == 'completed' else 0,
                        created_at=current_date,
                        completed_at=current_date if status == 'completed' else None,
                    )
                    created_count += 1

    logger.info(f"Generated {created_count} synthetic bookings over {weeks} weeks")
    return created_count


# ── Forecast Summary ───────────────────────────────────────────────

def get_forecast_summary(region='Delhi NCR'):
    """
    Get a summary of forecasts for the admin dashboard.
    Returns aggregated data for charts and stats.
    """
    from cooperative_admin.models import DemandForecast

    today = timezone.now().date()
    week_later = today + timedelta(days=7)

    forecasts = DemandForecast.objects.filter(
        region=region,
        forecast_date__gte=today,
        forecast_date__lte=week_later,
    )

    # Group by service category
    by_category = defaultdict(lambda: {'total_demand': 0, 'days': [], 'shortages': 0})
    for f in forecasts:
        cat = f.get_service_category_display()
        by_category[cat]['total_demand'] += f.predicted_demand
        by_category[cat]['days'].append({
            'date': f.forecast_date.strftime('%d %b'),
            'demand': f.predicted_demand,
            'shortage': f.is_shortage,
        })
        if f.is_shortage:
            by_category[cat]['shortages'] += 1

    # Total shortages
    total_shortages = forecasts.filter(is_shortage=True).count()
    total_forecasts = forecasts.count()

    return {
        'by_category': dict(by_category),
        'total_shortages': total_shortages,
        'total_forecasts': total_forecasts,
        'shortage_percentage': round(total_shortages / total_forecasts * 100, 1) if total_forecasts > 0 else 0,
    }
