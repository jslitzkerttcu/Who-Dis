"""Admin interface for employee profiles management."""

import logging
from typing import Dict, Any, Optional
from flask import render_template_string
from datetime import datetime

from app.database import db
from app.models.employee_profiles import EmployeeProfiles
from app.services.refresh_employee_profiles import employee_profiles_service
from app.utils.error_handler import handle_service_errors

logger = logging.getLogger(__name__)


@handle_service_errors(service_name="admin_employee_profiles", default_return={})
def get_employee_profiles_stats() -> Dict[str, Any]:
    """Get employee profiles statistics for admin dashboard."""
    try:
        # Add additional statistics
        total_profiles = EmployeeProfiles.query.count()
        locked_profiles = EmployeeProfiles.query.filter_by(ks_login_lock="L").count()
        profiles_with_photos = EmployeeProfiles.query.filter(
            EmployeeProfiles.photo_data.isnot(None)
        ).count()

        # Get most recent refresh
        latest_profile = EmployeeProfiles.query.order_by(
            EmployeeProfiles.updated_at.desc()
        ).first()

        last_refresh = latest_profile.updated_at if latest_profile else None

        return {
            "total_profiles": total_profiles,
            "locked_profiles": locked_profiles,
            "profiles_with_photos": profiles_with_photos,
            "profiles_without_photos": total_profiles - profiles_with_photos,
            "last_refresh": last_refresh.isoformat() if last_refresh else None,
            "last_refresh_formatted": last_refresh.strftime("%m/%d/%Y %I:%M %p")
            if last_refresh
            else "Never",
        }

    except Exception as e:
        logger.error(f"Error getting employee profiles stats: {str(e)}")
        return {
            "total_profiles": 0,
            "locked_profiles": 0,
            "profiles_with_photos": 0,
            "profiles_without_photos": 0,
            "last_refresh": None,
            "last_refresh_formatted": "Error",
            "error": str(e),
        }


@handle_service_errors(service_name="admin_employee_profiles", default_return=[])
def get_employee_profiles_list(
    page: int = 1,
    per_page: int = 20,
    filter_role: Optional[str] = None,
    filter_lock: Optional[str] = None,
    filter_expected_role: Optional[str] = None,
) -> Dict[str, Any]:
    """Get paginated list of employee profiles with filters."""
    try:
        # Use a custom query to select only needed fields plus photo existence
        from sqlalchemy import case

        # Create a query that includes a computed field for photo existence
        query = db.session.query(
            EmployeeProfiles.upn,
            EmployeeProfiles.ks_user_serial,
            EmployeeProfiles.ks_last_login_time,
            EmployeeProfiles.ks_login_lock,
            EmployeeProfiles.live_role,
            EmployeeProfiles.test_role,
            EmployeeProfiles.keystone_expected_role,
            EmployeeProfiles.ukg_job_code,
            EmployeeProfiles.created_at,
            EmployeeProfiles.updated_at,
            case((EmployeeProfiles.photo_data.isnot(None), True), else_=False).label(
                "has_photo"
            ),
        )

        # Apply filters
        if filter_role:
            query = query.filter(EmployeeProfiles.live_role.ilike(f"%{filter_role}%"))

        if filter_lock and filter_lock in ["L", "N"]:
            query = query.filter(EmployeeProfiles.ks_login_lock == filter_lock)

        if filter_expected_role:
            query = query.filter(
                EmployeeProfiles.keystone_expected_role.ilike(
                    f"%{filter_expected_role}%"
                )
            )

        # Order by most recently updated
        query = query.order_by(EmployeeProfiles.updated_at.desc())

        # Calculate pagination manually
        total = query.count()
        offset = (page - 1) * per_page
        items = query.offset(offset).limit(per_page).all()

        # Calculate pagination info
        pages = (total + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < pages
        prev_num = page - 1 if has_prev else None
        next_num = page + 1 if has_next else None

        profiles = []
        for row in items:
            # Build profile data from query row
            profile_data = {
                "upn": row.upn,
                "user_serial": row.ks_user_serial,
                "last_login": row.ks_last_login_time.isoformat()
                if row.ks_last_login_time
                else None,
                "is_locked": row.ks_login_lock == "L",
                "lock_status": "Locked" if row.ks_login_lock == "L" else "Unlocked",
                "live_role": row.live_role,
                "test_role": row.test_role,
                "job_code": row.ukg_job_code,
                "expected_role": row.keystone_expected_role,
                "has_photo": row.has_photo,
                "last_updated": row.updated_at.isoformat() if row.updated_at else None,
                "photo_preview": None,
            }
            profiles.append(profile_data)

        return {
            "profiles": profiles,
            "pagination": {
                "page": page,
                "pages": pages,
                "per_page": per_page,
                "total": total,
                "has_prev": has_prev,
                "has_next": has_next,
                "prev_num": prev_num,
                "next_num": next_num,
            },
        }

    except Exception as e:
        logger.error(f"Error getting employee profiles list: {str(e)}")
        return {
            "profiles": [],
            "pagination": {
                "page": 1,
                "pages": 0,
                "per_page": per_page,
                "total": 0,
                "has_prev": False,
                "has_next": False,
                "prev_num": None,
                "next_num": None,
            },
            "error": str(e),
        }


@handle_service_errors(service_name="admin_employee_profiles", default_return={})
def refresh_all_employee_profiles() -> Dict[str, Any]:
    """Trigger full refresh of all employee profiles."""
    try:
        logger.info("Admin initiated full employee profiles refresh")

        start_time = datetime.now()
        result = employee_profiles_service.refresh_all_profiles()
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()

        return {
            "success": True,
            "result": result,
            "duration_seconds": duration,
            "message": f"Refresh completed: {result.get('success', 0)} successful, {result.get('failed', 0)} failed, {result.get('total', 0)} total",
        }

    except Exception as e:
        logger.error(f"Error during admin employee profiles refresh: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Refresh failed: {str(e)}",
        }


@handle_service_errors(service_name="admin_employee_profiles", default_return=None)
def get_employee_profile_by_upn(upn: str) -> Optional[Dict[str, Any]]:
    """Get specific employee profile by UPN."""
    try:
        profile_record = EmployeeProfiles.get_by_upn(upn)

        if profile_record:
            profile = profile_record.get_display_info()
            return profile

        return None

    except Exception as e:
        logger.error(f"Error getting employee profile for {upn}: {str(e)}")
        return None


def render_employee_profiles_table(profiles_data: Dict[str, Any]) -> str:
    """Render employee profiles table for HTMX response."""
    table_template = """
    {% if profiles_data.error %}
        <tr>
            <td colspan="8" class="px-6 py-4 text-center text-red-600">
                <i class="fas fa-exclamation-triangle mr-2"></i>
                Error loading profiles: {{ profiles_data.error }}
            </td>
        </tr>
    {% else %}
        {% for profile in profiles_data.profiles %}
        <tr class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center">
                    {% if profile.has_photo %}
                        <div class="relative photo-hover-container mr-3">
                            <img src="{{ url_for('admin.api_employee_profile_photo', upn=profile.upn) }}" 
                                 alt="Profile photo" 
                                 class="h-10 w-10 rounded-full object-cover border border-gray-200 lazy-photo cursor-pointer"
                                 loading="lazy"
                                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                            <div class="h-10 w-10 rounded-full bg-gray-200 items-center justify-center border border-gray-300" style="display: none;">
                                <i class="fas fa-user text-gray-500"></i>
                            </div>
                            <!-- Hover overlay with larger image -->
                            <div class="photo-hover-overlay hidden bg-white rounded-lg shadow-2xl border border-gray-300 p-2" 
                                 data-upn="{{ profile.upn }}">
                                <img src="{{ url_for('admin.api_employee_profile_photo', upn=profile.upn) }}" 
                                     alt="Profile photo enlarged" 
                                     class="w-32 h-32 rounded-lg object-cover">
                                <div class="text-xs text-gray-600 text-center mt-2 font-medium">{{ profile.upn }}</div>
                            </div>
                        </div>
                    {% else %}
                        <div class="h-10 w-10 rounded-full bg-gray-200 flex items-center justify-center mr-3 border border-gray-300">
                            <i class="fas fa-user text-gray-500"></i>
                        </div>
                    {% endif %}
                    <div>
                        <div class="text-sm font-medium text-gray-900">{{ profile.upn }}</div>
                        {% if profile.user_serial %}
                            <div class="text-sm text-gray-500">Serial: {{ profile.user_serial }}</div>
                        {% endif %}
                    </div>
                </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                {% if profile.live_role %}
                    <span class="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                        {{ profile.live_role }}
                    </span>
                {% else %}
                    <span class="text-gray-400 text-sm">No role</span>
                {% endif %}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                {% if profile.expected_role %}
                    <span class="px-2 py-1 text-xs font-medium bg-purple-100 text-purple-800 rounded-full">
                        {{ profile.expected_role }}
                    </span>
                {% else %}
                    <span class="text-gray-400 text-sm">Not mapped</span>
                {% endif %}
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                {% if profile.is_locked %}
                    <span class="px-2 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full">
                        <i class="fas fa-lock mr-1"></i>Locked
                    </span>
                {% else %}
                    <span class="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">
                        <i class="fas fa-unlock mr-1"></i>Unlocked
                    </span>
                {% endif %}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ profile.job_code or '-' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ profile.last_login or 'Never' }}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-center">
                {% if profile.has_photo %}
                    <i class="fas fa-camera text-green-600" title="Has photo"></i>
                {% else %}
                    <i class="fas fa-camera text-gray-300" title="No photo"></i>
                {% endif %}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ profile.last_updated or 'Unknown' }}
            </td>
        </tr>
        {% endfor %}
        
        {% if not profiles_data.profiles %}
        <tr>
            <td colspan="8" class="px-6 py-4 text-center text-gray-500">
                No employee profiles found
            </td>
        </tr>
        {% endif %}
    {% endif %}
    """

    return render_template_string(table_template, profiles_data=profiles_data)


def render_employee_profiles_pagination(pagination_data: Dict[str, Any]) -> str:
    """Render pagination controls for employee profiles."""
    pagination_template = """
    <div class="flex items-center justify-between px-6 py-3 bg-white border-t border-gray-200">
        <div class="flex-1 flex justify-between sm:hidden">
            {% if pagination_data.has_prev %}
                <button hx-get="{{ url_for('admin.api_employee_profiles') }}?page={{ pagination_data.prev_num }}"
                        hx-target="#employee-profiles-content"
                        hx-swap="innerHTML"
                        class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
                    Previous
                </button>
            {% endif %}
            {% if pagination_data.has_next %}
                <button hx-get="{{ url_for('admin.api_employee_profiles') }}?page={{ pagination_data.next_num }}"
                        hx-target="#employee-profiles-content"
                        hx-swap="innerHTML"
                        class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50">
                    Next
                </button>
            {% endif %}
        </div>
        <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
                <p class="text-sm text-gray-700">
                    Showing page <span class="font-medium">{{ pagination_data.page }}</span> of <span class="font-medium">{{ pagination_data.pages }}</span>
                    (<span class="font-medium">{{ pagination_data.total }}</span> total profiles)
                </p>
            </div>
            <div>
                <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                    {% if pagination_data.has_prev %}
                        <button hx-get="{{ url_for('admin.api_employee_profiles') }}?page={{ pagination_data.prev_num }}"
                                hx-target="#employee-profiles-content"
                                hx-swap="innerHTML"
                                class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">
                            <i class="fas fa-chevron-left"></i>
                        </button>
                    {% endif %}
                    
                    <span class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">
                        {{ pagination_data.page }} / {{ pagination_data.pages }}
                    </span>
                    
                    {% if pagination_data.has_next %}
                        <button hx-get="{{ url_for('admin.api_employee_profiles') }}?page={{ pagination_data.next_num }}"
                                hx-target="#employee-profiles-content"
                                hx-swap="innerHTML"
                                class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50">
                            <i class="fas fa-chevron-right"></i>
                        </button>
                    {% endif %}
                </nav>
            </div>
        </div>
    </div>
    """

    return render_template_string(pagination_template, pagination_data=pagination_data)


def render_employee_profiles_with_pagination(profiles_data: Dict[str, Any]) -> str:
    """Render both employee profiles table and pagination controls."""
    template = """
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Employee
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Live Role
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Expected Role
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Lock Status
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Job Code
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Last Login
                    </th>
                    <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Photo
                    </th>
                    <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Last Updated
                    </th>
                </tr>
            </thead>
            <tbody class="bg-white divide-y divide-gray-200">
                {{ table_content | safe }}
            </tbody>
        </table>
    </div>
    
    <!-- Pagination -->
    {{ pagination_content | safe }}
    """

    table_content = render_employee_profiles_table(profiles_data)
    pagination_content = render_employee_profiles_pagination(
        profiles_data["pagination"]
    )

    return render_template_string(
        template, table_content=table_content, pagination_content=pagination_content
    )
