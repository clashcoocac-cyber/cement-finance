# Cement Finance Management System

## Overview
Clean, minimalistic Django application for managing cement sales, customer debts, and payments. The system tracks orders, calculates remaining debts, and provides comprehensive reporting.

## Project Structure

```
cement-finance/
├── app/                    # Clean, restructured application
│   ├── models.py          # Database models with clean structure
│   ├── views.py           # View controllers with inheritance
│   ├── forms.py           # Form handling with base classes
│   ├── filters.py         # Data filtering
│   ├── services.py        # Business logic services
│   ├── utils.py           # Utility functions
│   ├── constants.py       # Application constants
│   ├── admin.py           # Admin interface
│   ├── tests.py           # Comprehensive test cases
│   ├── urls.py            # URL routing
│   ├── settings.py        # Django settings
│   ├── wsgi.py            # WSGI configuration
│   ├── asgi.py            # ASGI configuration
│   ├── manage.py          # Django management
│   ├── requirements.txt    # Dependencies
│   └── README.md          # App documentation
├── finance/               # Original application (for reference)
├── config/                # Original configuration
├── templates/             # HTML templates
├── static/                # Static files
└── README.md              # This file
```

## Key Improvements in App Structure

### 1. Clean Code Principles
- **Separation of Concerns**: Business logic moved to services
- **DRY Principle**: Reusable utility functions
- **Single Responsibility**: Each class has a focused purpose
- **Type Hints**: Full type annotation for better code clarity

### 2. Better Organization
- **Service Layer**: Business logic separated from views
- **Utility Functions**: Common operations centralized
- **Constants**: Application configuration centralized
- **Base Classes**: Inheritance for common functionality

### 3. Enhanced Features
- **Comprehensive Testing**: Full test coverage
- **Better Validation**: Enhanced form validation
- **Error Handling**: Improved error management
- **Documentation**: Complete code documentation

## Business Logic

### Customer Management
- Track customer information (name, phone, address)
- Manage initial debt and current total debt
- Automatic debt calculation based on orders and payments

### Order Management
- Create cement orders with automatic calculations
- Track quantity, price per kg, road costs
- Calculate total price, total sum, and remaining debt
- Link orders to customers and cement types

### Payment Tracking
- Record customer payments with different payment types
- Automatic debt reduction on payments
- Complete payment history tracking

### Cement Types
- Manage different cement types with color coding
- Track quantities sold by type and month
- Statistical analysis of popular types

## Installation

### Prerequisites
- Python 3.8+
- Django 4.2+
- SQLite (or PostgreSQL/MySQL)

### Setup
1. Clone the repository
2. Navigate to the app directory: `cd app`
3. Install dependencies: `pip install -r requirements.txt`
4. Run migrations: `python manage.py migrate`
5. Create superuser: `python manage.py createsuperuser`
6. Run the server: `python manage.py runserver`

## Usage

### Dashboard
- View all orders with filtering options
- Customer-specific order history
- Real-time totals and statistics

### Customer Management
- Add new customers with initial debt
- Edit customer information
- View debt status and history

### Order Management
- Create orders with automatic calculations
- Edit orders with debt recalculation
- Delete orders with proper debt adjustment

### Payment Management
- Record customer payments
- Track payment history
- Monitor debt balances

### Statistics
- Overall business statistics
- Popular cement type analysis
- Revenue and debt trends

## Technical Features

### Database Design
- Optimized models with proper relationships
- Efficient queries with select_related
- Automatic calculations in model save methods

### Security
- Login required for all views
- Form validation and sanitization
- CSRF protection enabled

### Performance
- Efficient database queries
- Optimized template rendering
- Proper indexing for large datasets

## Code Quality

### Clean Architecture
- **Models**: Clean, focused database models
- **Views**: Organized with inheritance and common context
- **Forms**: Base classes with reusable functionality
- **Services**: Business logic separated from views

### Testing
- Comprehensive test coverage
- Model, form, and view tests
- Business logic validation

### Documentation
- Complete code documentation
- README files for each module
- Type hints throughout

## Migration from Original

The original `finance` app has been restructured into the clean `app` directory with:

1. **Better Organization**: Logical separation of concerns
2. **Service Layer**: Business logic moved to dedicated services
3. **Utility Functions**: Common operations centralized
4. **Constants**: Application configuration centralized
5. **Enhanced Testing**: Comprehensive test coverage
6. **Type Hints**: Better code clarity and IDE support

## Contributing

1. Follow clean code principles
2. Add comprehensive tests
3. Update documentation
4. Use type hints
5. Follow Django best practices

## License

This project is open source and available under the MIT License.
