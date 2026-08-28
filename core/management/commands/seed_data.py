"""
Seed data management command for Gig Saarthi.
Creates realistic demo data for hackathon demos.

Usage: python manage.py seed_data
"""

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with realistic demo data for Gig Saarthi'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Seeding Gig Saarthi database...\n'))

        self.create_cooperatives()
        self.create_skill_categories_and_skills()
        self.create_workers()
        self.create_customers()
        self.create_service_categories()
        self.create_bookings()
        self.create_sample_reviews()

        self.stdout.write(self.style.SUCCESS('\nDatabase seeded successfully!'))
        self.stdout.write(self.style.SUCCESS(
            f'   Created: {User.objects.count()} users, '
            f'{self._count("cooperative_admin.Cooperative")} cooperatives, '
            f'{self._count("workers.WorkerProfile")} worker profiles'
        ))

    def _count(self, model_path):
        app_label, model_name = model_path.split('.')
        from django.apps import apps
        return apps.get_model(app_label, model_name).objects.count()

    def create_cooperatives(self):
        """Create 5 cooperatives across different regions."""
        from cooperative_admin.models import Cooperative

        cooperatives_data = [
            {
                'name': 'Gig Saarthi Urban Cooperative',
                'registration_number': 'COOP-2024-001',
                'region': 'South Delhi',
                'district': 'New Delhi',
                'state': 'Delhi',
                'federation_level': 'district',
                'contact_person': 'Rajesh Kumar',
                'contact_phone': '+919876543210',
            },
            {
                'name': 'Gramin Seva Sahakari Samiti',
                'registration_number': 'COOP-2024-002',
                'region': 'Gurugram Rural',
                'district': 'Gurugram',
                'state': 'Haryana',
                'federation_level': 'village',
                'contact_person': 'Sunita Devi',
                'contact_phone': '+919876543211',
            },
            {
                'name': 'Noida Workers Cooperative',
                'registration_number': 'COOP-2024-003',
                'region': 'Noida Sector 62',
                'district': 'Gautam Buddh Nagar',
                'state': 'Uttar Pradesh',
                'federation_level': 'district',
                'contact_person': 'Amit Sharma',
                'contact_phone': '+919876543212',
            },
            {
                'name': 'Faridabad Mahila Cooperative',
                'registration_number': 'COOP-2024-004',
                'region': 'Faridabad',
                'district': 'Faridabad',
                'state': 'Haryana',
                'federation_level': 'village',
                'contact_person': 'Priya Gupta',
                'contact_phone': '+919876543213',
            },
            {
                'name': 'State Level Federation of Gig Workers',
                'registration_number': 'COOP-2024-005',
                'region': 'Delhi NCR',
                'district': 'All NCR',
                'state': 'Delhi',
                'federation_level': 'state',
                'contact_person': 'Vikram Singh',
                'contact_phone': '+919876543214',
            },
        ]

        for data in cooperatives_data:
            coop, created = Cooperative.objects.get_or_create(
                registration_number=data['registration_number'],
                defaults={**data, 'is_active': True}
            )
            if created:
                self.stdout.write(f'  [OK] Cooperative: {coop.name}')

    def create_skill_categories_and_skills(self):
        """Create skill categories and associated skills."""
        from workers.models import SkillCategory, Skill

        categories_data = {
            'Plumbing': {
                'icon': '🔧',
                'skills': ['Pipe Repair', 'Tap Installation', 'Drainage Cleaning', 'Bathroom Renovation'],
            },
            'Electrical': {
                'icon': '⚡',
                'skills': ['Wiring', 'Switch Board Repair', 'Inverter Installation', 'Fan/Motor Repair'],
            },
            'Cleaning': {
                'icon': '🧹',
                'skills': ['Home Deep Cleaning', 'Office Cleaning', 'Carpet Cleaning', 'Kitchen Cleaning'],
            },
            'Carpentry': {
                'icon': '🪚',
                'skills': ['Furniture Repair', 'Door/Window Fixing', 'Shelf Installation', 'Wood Polishing'],
            },
            'Cooking': {
                'icon': '👨‍🍳',
                'skills': ['North Indian Cuisine', 'South Indian Cuisine', 'Baking', 'Tiffin Service'],
            },
            'Elderly Care': {
                'icon': '🏥',
                'skills': ['Personal Care', 'Medical Assistance', 'Companionship', 'Physiotherapy Support'],
            },
            'Gardening': {
                'icon': '🌿',
                'skills': ['Lawn Mowing', 'Plant Care', 'Landscaping', 'Pest Control'],
            },
            'Painting': {
                'icon': '🎨',
                'skills': ['Interior Painting', 'Exterior Painting', 'Wallpaper Installation', 'Texture Work'],
            },
        }

        for cat_name, cat_data in categories_data.items():
            category, _ = SkillCategory.objects.get_or_create(
                name=cat_name,
                defaults={'icon': cat_data['icon'], 'description': f'Professional {cat_name.lower()} services'}
            )
            for skill_name in cat_data['skills']:
                Skill.objects.get_or_create(
                    name=skill_name,
                    category=category,
                    defaults={'description': f'{skill_name} services'}
                )

        self.stdout.write(f'  [OK] Created {SkillCategory.objects.count()} skill categories with {Skill.objects.count()} skills')

    def create_workers(self):
        """Create 30 worker users with profiles."""
        from workers.models import WorkerProfile, Skill, SkillCategory
        from cooperative_admin.models import Cooperative

        cooperatives = list(Cooperative.objects.all())
        all_skills = list(Skill.objects.all())

        worker_names = [
            ('Ramesh', 'Kumar', '+919800000001', 'Plumbing'),
            ('Suresh', 'Patel', '+919800000002', 'Electrical'),
            ('Dinesh', 'Yadav', '+919800000003', 'Cleaning'),
            ('Mahesh', 'Singh', '+919800000004', 'Carpentry'),
            ('Rakesh', 'Verma', '+919800000005', 'Plumbing'),
            ('Mukesh', 'Joshi', '+919800000006', 'Electrical'),
            ('Ashok', 'Meena', '+919800000007', 'Cleaning'),
            ('Sunil', 'Chauhan', '+919800000008', 'Cooking'),
            ('Vikash', 'Tiwari', '+919800000009', 'Elderly Care'),
            ('Deepak', 'Rao', '+919800000010', 'Gardening'),
            ('Rajesh', 'Pandey', '+919800000011', 'Painting'),
            ('Manoj', 'Reddy', '+919800000012', 'Plumbing'),
            ('Sanjay', 'Nair', '+919800000013', 'Electrical'),
            ('Arun', 'Desai', '+919800000014', 'Carpentry'),
            ('Vinod', 'Bhatt', '+919800000015', 'Cleaning'),
            ('Ravi', 'Iyer', '+919800000016', 'Cooking'),
            ('Santosh', 'Menon', '+919800000017', 'Elderly Care'),
            ('Prakash', 'Sharma', '+919800000018', 'Gardening'),
            ('Kamal', 'Mishra', '+919800000019', 'Painting'),
            ('Naresh', 'Gupta', '+919800000020', 'Plumbing'),
            ('Bharat', 'Thakur', '+919800000021', 'Electrical'),
            ('Jagdish', 'Pillai', '+919800000022', 'Cleaning'),
            ('Anil', 'Rao', '+919800000023', 'Carpentry'),
            ('Raj Kumar', 'Bose', '+919800000024', 'Cooking'),
            ('Lalit', 'Saxena', '+919800000025', 'Elderly Care'),
            ('Harish', 'Kulkarni', '+919800000026', 'Gardening'),
            ('Devendra', 'Chatterjee', '+919800000027', 'Painting'),
            ('Pankaj', 'Bhatt', '+919800000028', 'Plumbing'),
            ('Shankar', 'Prasad', '+919800000029', 'Electrical'),
            ('Murli', 'Dubey', '+919800000030', 'Cleaning'),
        ]

        # Delhi NCR approximate coordinates
        locations = [
            (28.6139, 77.2090), (28.5244, 77.2066), (28.6353, 77.2250),
            (28.4595, 77.0266), (28.5802, 77.3184), (28.4089, 77.0434),
            (28.6692, 77.2300), (28.5412, 77.2580), (28.7041, 77.1025),
            (28.4811, 77.0854), (28.6507, 77.2334), (28.5244, 77.3764),
            (28.6139, 77.2295), (28.4474, 77.0123), (28.5821, 77.3107),
            (28.6315, 77.2167), (28.6482, 77.2900), (28.6779, 77.0869),
            (28.5011, 77.4047), (28.6803, 77.3530), (28.6284, 77.2180),
            (28.5388, 77.2620), (28.4734, 77.0583), (28.6398, 77.2780),
            (28.5733, 77.3872), (28.6871, 77.0753), (28.6607, 77.4170),
            (28.6260, 77.2430), (28.5082, 77.3890), (28.7230, 77.1180),
        ]

        availabilities = ['available', 'available', 'available', 'busy', 'offline']

        for i, (first_name, last_name, phone, primary_category) in enumerate(worker_names):
            username = f'worker_{i+1:03d}'
            if User.objects.filter(username=username).exists():
                continue

            user = User.objects.create_user(
                username=username,
                email=f'{username}@gigsaarthi.in',
                first_name=first_name,
                last_name=last_name,
                phone_number=phone,
                role='worker',
                password='worker123',
                is_phone_verified=True,
                preferred_language=random.choice(['en', 'hi']),
            )

            # Get skills from primary category + some random extras
            primary_skills = Skill.objects.filter(category__name=primary_category)[:2]
            extra_skills = random.sample(all_skills, min(2, len(all_skills)))
            worker_skills = list(set(list(primary_skills) + extra_skills))

            lat, lng = locations[i % len(locations)]
            # Add slight randomness to location
            lat += random.uniform(-0.02, 0.02)
            lng += random.uniform(-0.02, 0.02)

            profile = WorkerProfile.objects.create(
                user=user,
                experience_years=random.randint(1, 15),
                cooperative=random.choice(cooperatives),
                bio=f'Experienced {primary_category.lower()} professional with {random.randint(1, 15)} years of expertise.',
                availability_status=random.choice(availabilities),
                current_latitude=round(lat, 6),
                current_longitude=round(lng, 6),
                avg_rating=round(random.uniform(3.5, 5.0), 2),
                total_jobs_completed=random.randint(5, 200),
                total_reviews=random.randint(3, 50),
                is_verified=random.choice([True, True, True, False]),
                id_proof_type=random.choice(['Aadhaar', 'PAN', 'Voter ID']),
                bank_account_number=f'{random.randint(1000000000, 9999999999)}',
                bank_ifsc_code=f'{"SBIN"}{random.randint(100000, 999999)}',
                bank_name=random.choice(['SBI', 'HDFC', 'ICICI', 'PNB', 'BOB']),
                upi_id=f'{username}@paytm',
            )
            profile.skills.set(worker_skills)

        self.stdout.write(f'  [OK] Created {len(worker_names)} workers with profiles')

    def create_customers(self):
        """Create 15 customer users with profiles."""
        from customers.models import CustomerProfile

        customer_data = [
            ('Priyanka', 'Sharma', '+919700000001'),
            ('Anjali', 'Mehta', '+919700000002'),
            ('Rahul', 'Aggarwal', '+919700000003'),
            ('Neha', 'Sinha', '+919700000004'),
            ('Vishal', 'Choudhary', '+919700000005'),
            ('Kavita', 'Rao', '+919700000006'),
            ('Amit', 'Bansal', '+919700000007'),
            ('Shweta', 'Malhotra', '+919700000008'),
            ('Deepak', 'Sethi', '+919700000009'),
            ('Ritu', 'Kapoor', '+919700000010'),
            ('Manish', 'Jain', '+919700000011'),
            ('Pooja', 'Agarwal', '+919700000012'),
            ('Sachin', 'Tiwari', '+919700000013'),
            ('Divya', 'Bhatnagar', '+919700000014'),
            ('Karan', 'Mehra', '+919700000015'),
        ]

        addresses = [
            '42, Hauz Khas Village, New Delhi 110016',
            '15, Sector 44, Gurugram 122003',
            '88, Lajpat Nagar, New Delhi 110024',
            '23, Sector 62, Noida 201301',
            '67, Dwarka Sector 7, New Delhi 110075',
            '31, Saket, New Delhi 110017',
            '9, Vasant Kunj, New Delhi 110070',
            '55, Connaught Place, New Delhi 110001',
            '72, Greater Kailash I, New Delhi 110048',
            '14, Paschim Vihar, New Delhi 110063',
            '39, Rohini Sector 3, New Delhi 110085',
            '8, Janakpuri, New Delhi 110058',
            '61, Pitampura, New Delhi 110034',
            '27, Uttam Nagar, New Delhi 110059',
            '45, Malviya Nagar, New Delhi 110017',
        ]

        for i, (first_name, last_name, phone) in enumerate(customer_data):
            username = f'customer_{i+1:03d}'
            if User.objects.filter(username=username).exists():
                continue

            user = User.objects.create_user(
                username=username,
                email=f'{username}@gigsaarthi.in',
                first_name=first_name,
                last_name=last_name,
                phone_number=phone,
                role='customer',
                password='customer123',
                is_phone_verified=True,
            )

            # Delhi NCR coordinates for customers
            lat = round(28.6139 + random.uniform(-0.05, 0.05), 6)
            lng = round(77.2090 + random.uniform(-0.05, 0.05), 6)

            CustomerProfile.objects.create(
                user=user,
                default_address=addresses[i % len(addresses)],
                default_latitude=lat,
                default_longitude=lng,
            )

        self.stdout.write(f'  [OK] Created {len(customer_data)} customers with profiles')

    def create_service_categories(self):
        """Create service categories."""
        from bookings.models import ServiceCategory
        from workers.models import SkillCategory

        services_data = [
            ('Home Cleaning', '🧹', 'Professional home and office cleaning services', 399),
            ('Plumbing Repair', '🔧', 'Expert plumbing repair and installation', 299),
            ('Electrical Work', '⚡', 'Licensed electrical repair and wiring services', 349),
            ('Carpentry & Woodwork', '🪚', 'Furniture repair, installation, and woodwork', 449),
            ('Cooking & Tiffin', '👨‍🍳', 'Home cooking and tiffin services', 599),
            ('Elderly Care', '🏥', 'Compassionate elderly care and medical assistance', 699),
            ('Gardening & Landscaping', '🌿', 'Garden maintenance and landscaping', 349),
            ('Painting Services', '🎨', 'Interior and exterior painting', 499),
        ]

        for name, icon, description, base_price in services_data:
            service, _ = ServiceCategory.objects.get_or_create(
                name=name,
                defaults={
                    'icon': icon,
                    'description': description,
                    'base_price': Decimal(str(base_price)),
                    'is_active': True
                }
            )

        self.stdout.write(f'  [OK] Created {ServiceCategory.objects.count()} service categories')

        # Link skills to service categories
        from workers.models import SkillCategory, Skill
        skill_map = {
            'Carpentry & Woodwork': 'Carpentry',
            'Cooking & Tiffin': 'Cooking',
            'Elderly Care': 'Elderly Care',
            'Electrical Work': 'Electrical',
            'Gardening & Landscaping': 'Gardening',
            'Home Cleaning': 'Cleaning',
            'Painting Services': 'Painting',
            'Plumbing Repair': 'Plumbing',
        }
        for cat_name, skill_cat_name in skill_map.items():
            try:
                sc = ServiceCategory.objects.get(name=cat_name)
                skills = Skill.objects.filter(category__name=skill_cat_name)
                sc.related_skills.set(skills)
            except ServiceCategory.DoesNotExist:
                pass
        self.stdout.write(f'  [OK] Linked skills to service categories')

    def create_bookings(self):
        """Create 40 sample bookings with various statuses."""
        from bookings.models import Booking, ServiceCategory, BookingStatusHistory

        customers = list(User.objects.filter(role='customer'))
        workers = list(User.objects.filter(role='worker'))
        categories = list(ServiceCategory.objects.all())

        if not customers or not workers:
            self.stdout.write(self.style.WARNING('  [WARN] No customers or workers to create bookings'))
            return

        now = timezone.now()
        statuses = [
            'completed', 'completed', 'completed', 'completed',
            'in_progress', 'in_progress',
            'accepted',
            'matched',
            'pending',
            'cancelled_by_customer',
            'disputed',
        ]

        addresses = [
            '42, Hauz Khas Village, New Delhi 110016',
            '15, Sector 44, Gurugram 122003',
            '88, Lajpat Nagar, New Delhi 110024',
            '23, Sector 62, Noida 201301',
            '67, Dwarka Sector 7, New Delhi 110075',
        ]

        descriptions = [
            'Need urgent repair for leaking pipe in bathroom',
            'AC not cooling properly, needs servicing',
            'Full home deep cleaning required before Diwali',
            'Kitchen tap is broken and needs replacement',
            'Need someone to fix the electrical wiring in bedroom',
            'Old furniture needs polishing and minor repair',
            'Looking for daily tiffin service for 2 people',
            'Need painting for 2BHK flat - interior walls',
            'Garden is overgrown, needs complete maintenance',
            'Elderly parent needs daily care attendant',
        ]

        for i in range(40):
            status = random.choice(statuses)
            days_ago = random.randint(0, 30)
            scheduled = now - timedelta(days=days_ago, hours=random.randint(-12, 12))
            is_emergency = random.random() < 0.15

            lat = round(28.6139 + random.uniform(-0.05, 0.05), 6)
            lng = round(77.2090 + random.uniform(-0.05, 0.05), 6)

            booking = Booking.objects.create(
                customer=random.choice(customers),
                worker=random.choice(workers) if status not in ('pending',) else None,
                service_category=random.choice(categories),
                description=random.choice(descriptions),
                scheduled_datetime=scheduled,
                is_emergency=is_emergency,
                status=status,
                address_text=random.choice(addresses),
                latitude=lat,
                longitude=lng,
                estimated_price=Decimal(str(random.randint(299, 999))),
                final_price=Decimal(str(random.randint(299, 999))) if status == 'completed' else 0,
                completed_at=now - timedelta(days=days_ago) if status == 'completed' else None,
                cancelled_at=now - timedelta(days=days_ago) if 'cancelled' in status else None,
            )

            # Add status history
            BookingStatusHistory.objects.create(
                booking=booking,
                status='pending',
                notes='Booking created'
            )

            if status != 'pending':
                BookingStatusHistory.objects.create(
                    booking=booking,
                    status=status,
                    notes=f'Status changed to {status}'
                )

        self.stdout.write(f'  [OK] Created {Booking.objects.count()} bookings')

    def create_sample_reviews(self):
        """Create reviews for completed bookings."""
        from bookings.models import Booking
        from ratings.models import Review

        completed_bookings = Booking.objects.filter(
            status='completed',
            worker__isnull=False
        ).exclude(review__isnull=False)[:20]

        comments = [
            'Excellent work! Very professional and punctual.',
            'Good service, would recommend to others.',
            'Satisfied with the work done. Fair pricing.',
            'Arrived on time and completed the work efficiently.',
            'Very polite and skilled worker. Will hire again.',
            'Work was decent, but could have been cleaner.',
            'Great experience overall! Five stars.',
            'Quick response and quality work.',
            'Friendly worker, did a thorough job.',
            'Reasonable prices and good quality work.',
        ]

        count = 0
        for booking in completed_bookings:
            if hasattr(booking, 'review'):
                continue

            Review.objects.create(
                booking=booking,
                customer=booking.customer,
                worker=booking.worker,
                overall_rating=random.randint(3, 5),
                punctuality_rating=random.randint(3, 5),
                quality_rating=random.randint(3, 5),
                comment=random.choice(comments),
            )
            count += 1

        self.stdout.write(f'  [OK] Created {count} reviews')
