// EventHub - Main JavaScript File

// DOM Content Loaded Event
document.addEventListener('DOMContentLoaded', function() {
    initializeEventHub();
});

// Initialize main functions
function initializeEventHub() {
    initializeNavbar();
    initializeNotifications();
    initializeSearch();
    initializeScrollEffects();
    initializeTooltips();
    initializeBackToTop();
}

// Navbar Functions
function initializeNavbar() {
    // Add active class to current page nav link
    const currentLocation = location.pathname;
    const menuItems = document.querySelectorAll('.navbar-nav .nav-link');
    
    menuItems.forEach(item => {
        if (item.getAttribute('href') === currentLocation) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Mobile menu auto-close on item click
    const navbarCollapse = document.querySelector('.navbar-collapse');
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth < 992) {
                const bsCollapse = new bootstrap.Collapse(navbarCollapse, {
                    toggle: false
                });
                bsCollapse.hide();
            }
        });
    });
}

// Notification Functions
function initializeNotifications() {
    // Mark notification as read when clicked
    const notificationItems = document.querySelectorAll('.notification-dropdown .dropdown-item');
    
    notificationItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            this.style.opacity = '0.7';
            this.style.backgroundColor = '#f8f9fa';
            
            // Here you would typically send an AJAX request to mark as read
            console.log('Notification marked as read');
        });
    });

    // Update notification count (example)
    updateNotificationCount();
}

// Search Functions
function initializeSearch() {
    const searchForm = document.querySelector('form[role="search"]');
    const searchInput = searchForm?.querySelector('input[type="search"]');
    
    if (searchForm && searchInput) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const query = searchInput.value.trim();
            
            if (query) {
                performSearch(query);
            } else {
                showAlert('Vui lòng nhập từ khóa tìm kiếm', 'warning');
            }
        });

        // Auto-suggestions (placeholder)
        searchInput.addEventListener('input', function() {
            const query = this.value.trim();
            if (query.length >= 2) {
                // Show search suggestions
                showSearchSuggestions(query);
            } else {
                hideSearchSuggestions();
            }
        });
    }
}

// Scroll Effects
function initializeScrollEffects() {
    let lastScrollTop = 0;
    const navbar = document.querySelector('.navbar');
    
    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        
        // Add shadow to navbar on scroll
        if (scrollTop > 10) {
            navbar.classList.add('shadow-lg');
        } else {
            navbar.classList.remove('shadow-lg');
        }
        
        // Hide/show navbar on scroll (optional)
        if (scrollTop > lastScrollTop && scrollTop > 100) {
            // Scrolling down
            navbar.style.transform = 'translateY(-100%)';
        } else {
            // Scrolling up
            navbar.style.transform = 'translateY(0)';
        }
        
        lastScrollTop = scrollTop;
    });
}

// Initialize Bootstrap Tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Back to Top Button
function initializeBackToTop() {
    const backToTopBtn = document.querySelector('.back-to-top button');
    
    if (backToTopBtn) {
        // Show/hide button based on scroll position
        window.addEventListener('scroll', function() {
            if (window.scrollY > 300) {
                backToTopBtn.parentElement.style.display = 'block';
                backToTopBtn.parentElement.style.opacity = '1';
            } else {
                backToTopBtn.parentElement.style.opacity = '0';
                setTimeout(() => {
                    if (window.scrollY <= 300) {
                        backToTopBtn.parentElement.style.display = 'none';
                    }
                }, 300);
            }
        });
    }
}

// Scroll to top function
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Search Functions
function performSearch(query) {
    // Show loading state
    showLoading();
    
    // Here you would typically send an AJAX request to your Flask backend
    console.log('Searching for:', query);
    
    // Simulate API call
    setTimeout(() => {
        hideLoading();
        // Redirect to search results page or update current page
        window.location.href = `/search?q=${encodeURIComponent(query)}`;
    }, 1000);
}

function showSearchSuggestions(query) {
    // Implementation for search suggestions dropdown
    console.log('Showing suggestions for:', query);
}

function hideSearchSuggestions() {
    // Hide search suggestions dropdown
    console.log('Hiding search suggestions');
}

// Notification Functions
function updateNotificationCount() {
    // This would typically fetch from your Flask backend
    const notificationBadge = document.querySelector('.nav-link .badge');
    
    // Example: Update badge count
    if (notificationBadge) {
        // You can update this based on actual notification count
        const count = 2; // This would come from your backend
        notificationBadge.textContent = count;
        
        if (count === 0) {
            notificationBadge.style.display = 'none';
        }
    }
}

// Utility Functions
function showAlert(message, type = 'info') {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show position-fixed" 
             style="top: 80px; right: 20px; z-index: 9999; min-width: 300px;" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', alertHtml);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        const alert = document.querySelector('.alert');
        if (alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }
    }, 5000);
}

function showLoading() {
    const searchBtn = document.querySelector('form[role="search"] button');
    if (searchBtn) {
        searchBtn.innerHTML = '<div class="loading"></div>';
        searchBtn.disabled = true;
    }
}

function hideLoading() {
    const searchBtn = document.querySelector('form[role="search"] button');
    if (searchBtn) {
        searchBtn.innerHTML = '<i class="fas fa-search"></i>';
        searchBtn.disabled = false;
    }
}

// Cart Functions (placeholder)
function addToCart(eventId, ticketTypeId) {
    console.log('Adding to cart:', eventId, ticketTypeId);
    showAlert('Đã thêm vào giỏ hàng!', 'success');
    updateCartCount();
}

function updateCartCount() {
    const cartBadge = document.querySelector('.nav-link .badge');
    if (cartBadge) {
        let currentCount = parseInt(cartBadge.textContent) || 0;
        cartBadge.textContent = currentCount + 1;
    }
}

// Event Listeners for dynamic content
document.addEventListener('click', function(e) {
    // Handle dynamic button clicks
    if (e.target.matches('.add-to-cart-btn')) {
        const eventId = e.target.dataset.eventId;
        const ticketTypeId = e.target.dataset.ticketTypeId;
        addToCart(eventId, ticketTypeId);
    }
    
    // Handle login/logout actions
    if (e.target.matches('.login-btn')) {
        showLoginModal();
    }
    
    if (e.target.matches('.logout-btn')) {
        handleLogout();
    }
});

// Authentication Functions (placeholder)
function showLoginModal() {
    // Implementation for login modal
    console.log('Showing login modal');
}

function handleLogout() {
    if (confirm('Bạn có chắc chắn muốn đăng xuất?')) {
        // Send logout request to Flask backend
        window.location.href = '/logout';
    }
}

// Form Validation Helper
function validateForm(formElement) {
    const inputs = formElement.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
        }
    });
    
    return isValid;
}

// Initialize form validation
document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function(e) {
        if (!validateForm(this)) {
            e.preventDefault();
            showAlert('Vui lòng điền đầy đủ thông tin bắt buộc', 'danger');
        }
    });
});

// Export functions for use in other scripts
window.EventHub = {
    showAlert,
    addToCart,
    updateCartCount,
    performSearch,
    scrollToTop,
    showLoading,
    hideLoading
};
