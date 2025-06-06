from flask import Blueprint, render_template, request, jsonify
from app.middleware.auth import require_role
from app.services.ldap_service import ldap_service
from app.services.genesys_service import genesys_service
from app.services.graph_service import graph_service
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

logger = logging.getLogger(__name__)

search_bp = Blueprint("search", __name__)

# Overall search timeout configuration
SEARCH_OVERALL_TIMEOUT = int(
    os.getenv("SEARCH_OVERALL_TIMEOUT", "20")
)  # Overall timeout in seconds


def merge_ldap_graph_data(ldap_data, graph_data):
    """
    Merge LDAP and Graph data into a single Azure AD result.
    Graph data takes priority in case of conflicts.
    """
    if not ldap_data and not graph_data:
        return None

    # Start with LDAP data as base
    merged = ldap_data.copy() if ldap_data else {}

    # Debug logging for password fields
    if ldap_data and "pwdLastSet" in ldap_data:
        logger.info(f"LDAP data contains pwdLastSet: {ldap_data['pwdLastSet']}")
    if ldap_data and "pwdExpires" in ldap_data:
        logger.info(f"LDAP data contains pwdExpires: {ldap_data['pwdExpires']}")

    # Remove LDAP thumbnail photo - we only want Graph photos
    if "thumbnailPhoto" in merged:
        logger.info("Removing LDAP thumbnail photo from merged data")
        del merged["thumbnailPhoto"]

    if graph_data:
        # Override/add Graph data (Graph takes priority)
        # Basic info
        if graph_data.get("displayName"):
            merged["displayName"] = graph_data["displayName"]
        if graph_data.get("mail"):
            merged["mail"] = graph_data["mail"]
        if graph_data.get("userPrincipalName"):
            merged["userPrincipalName"] = graph_data["userPrincipalName"]

        # Job info
        if graph_data.get("jobTitle"):
            merged["title"] = graph_data["jobTitle"]
        if graph_data.get("department"):
            merged["department"] = graph_data["department"]
        if graph_data.get("employeeId"):
            merged["employeeID"] = graph_data["employeeId"]

        # Manager info from Graph
        if graph_data.get("manager"):
            merged["manager"] = graph_data["manager"]
            merged["managerEmail"] = graph_data.get("managerEmail")

        # Office/Company info
        if graph_data.get("officeLocation"):
            merged["officeLocation"] = graph_data["officeLocation"]
        if graph_data.get("companyName"):
            merged["companyName"] = graph_data["companyName"]

        # Phone numbers - merge both sources
        phone_numbers = merged.get("phoneNumbers", {})
        if graph_data.get("phoneNumbers"):
            for phone_type, number in graph_data["phoneNumbers"].items():
                # Map Graph phone types to our standard types
                if phone_type == "mobile":
                    phone_numbers["mobile"] = number
                elif phone_type.startswith("business"):
                    phone_numbers["business"] = number
                else:
                    phone_numbers[phone_type] = number
        merged["phoneNumbers"] = phone_numbers

        # Account status from Graph
        if "accountEnabled" in graph_data:
            merged["enabled"] = graph_data["accountEnabled"]

        # Profile photo - ONLY use Graph photo
        if graph_data.get("photoUrl"):
            logger.info("Setting thumbnailPhoto from Graph photoUrl")
            merged["thumbnailPhoto"] = graph_data["photoUrl"]
        else:
            logger.info("No photoUrl in Graph data")

        # Additional name fields from Graph
        if graph_data.get("givenName"):
            merged["givenName"] = graph_data["givenName"]
        if graph_data.get("surname"):
            merged["surname"] = graph_data["surname"]

        # Employee type from Graph
        if graph_data.get("employeeType"):
            merged["employeeType"] = graph_data["employeeType"]

        # Graph ID
        if graph_data.get("id"):
            merged["graphId"] = graph_data["id"]

        # Additional Graph-only fields - only add if they exist
        if graph_data.get("address"):
            merged["address"] = graph_data["address"]
        if graph_data.get("lastPasswordChangeDateTime"):
            merged["lastPasswordChangeDateTime"] = graph_data[
                "lastPasswordChangeDateTime"
            ]
        if graph_data.get("createdDateTime"):
            merged["createdDateTime"] = graph_data["createdDateTime"]
        if graph_data.get("employeeHireDate"):
            merged["employeeHireDate"] = graph_data["employeeHireDate"]
        if graph_data.get("refreshTokensValidFromDateTime"):
            merged["refreshTokensValidFromDateTime"] = graph_data[
                "refreshTokensValidFromDateTime"
            ]
        if graph_data.get("signInSessionsValidFromDateTime"):
            merged["signInSessionsValidFromDateTime"] = graph_data[
                "signInSessionsValidFromDateTime"
            ]
        if graph_data.get("onPremisesLastSyncDateTime"):
            merged["onPremisesLastSyncDateTime"] = graph_data[
                "onPremisesLastSyncDateTime"
            ]
        if graph_data.get("passwordPolicies"):
            merged["passwordPolicies"] = graph_data["passwordPolicies"]
        if graph_data.get("dateOfBirth"):
            merged["dateOfBirth"] = graph_data["dateOfBirth"]

        # Mark as having Graph data
        merged["hasGraphData"] = True

    # Mark the data source
    merged["dataSource"] = "azureAD"

    return merged


@search_bp.route("/")
@require_role("viewer")
def index():
    return render_template("search/index.html")


@search_bp.route("/user", methods=["POST"])
@require_role("viewer")
def search_user():
    data = request.get_json()
    search_term = data.get("search_term", "").strip()
    genesys_user_id = data.get(
        "genesys_user_id"
    )  # For when user selects from multiple results
    ldap_user_dn = data.get(
        "ldap_user_dn"
    )  # For when user selects from multiple LDAP results
    graph_user_id = data.get(
        "graph_user_id"
    )  # For when user selects from multiple Graph results

    if not search_term:
        return jsonify({"error": "Search term is required"}), 400

    logger.info(
        f"Searching for user: {search_term}, specific genesys_id: {genesys_user_id}"
    )
    logger.info(f"Overall search timeout set to {SEARCH_OVERALL_TIMEOUT} seconds")

    # Get user info for audit logging
    user_email = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL-NAME", request.remote_user or "unknown"
    )
    user_role = getattr(request, "user_role", None)
    user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    user_agent = request.headers.get("User-Agent")

    ldap_result = None
    ldap_error = None
    ldap_multiple = False
    genesys_result = None
    genesys_error = None
    genesys_multiple = False
    graph_result = None
    graph_error = None
    graph_multiple = False

    # Use ThreadPoolExecutor for concurrent searches with timeout
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit both searches concurrently
        # For LDAP, either get specific user by DN or search
        if ldap_user_dn:
            ldap_future = executor.submit(ldap_service.get_user_by_dn, ldap_user_dn)
        else:
            ldap_future = executor.submit(ldap_service.search_user, search_term)

        # For Genesys, either search by ID or by term
        if genesys_user_id:
            genesys_future = executor.submit(
                genesys_service.get_user_by_id, genesys_user_id
            )
        else:
            genesys_future = executor.submit(genesys_service.search_user, search_term)

        # For Graph API, either get by ID or search
        if graph_user_id:
            graph_future = executor.submit(graph_service.get_user_by_id, graph_user_id)
        else:
            graph_future = executor.submit(graph_service.search_user, search_term)

        # Get LDAP results with timeout
        try:
            ldap_data = ldap_future.result(timeout=SEARCH_OVERALL_TIMEOUT)

            if ldap_user_dn and ldap_data:
                # Direct user lookup
                ldap_result = ldap_data
                logger.info(f"LDAP fetch for specific user DN: {ldap_user_dn}")
            elif ldap_data:
                if isinstance(ldap_data, dict) and ldap_data.get("multiple_results"):
                    ldap_multiple = True
                    ldap_result = ldap_data
                    logger.info(
                        f"LDAP search for '{search_term}' - Multiple results: {len(ldap_data.get('results', []))}"
                    )
                else:
                    # Single result
                    ldap_result = ldap_data
                    logger.info(f"LDAP search for '{search_term}' - Found single user")
            else:
                logger.info(f"LDAP search for '{search_term}' - No results")

        except FutureTimeoutError:
            logger.error(
                f"LDAP search timed out after {SEARCH_OVERALL_TIMEOUT} seconds"
            )
            ldap_error = f"LDAP search timed out after {SEARCH_OVERALL_TIMEOUT} seconds. Please try a more specific search term."
            ldap_future.cancel()
        except TimeoutError as e:
            # Handle our custom TimeoutError from LDAP service
            logger.error(f"LDAP timeout: {str(e)}")
            ldap_error = str(e)
        except Exception as e:
            logger.error(f"LDAP search error: {str(e)}")
            ldap_error = "LDAP search encountered an error"

        # Get Genesys results with timeout
        try:
            genesys_data = genesys_future.result(timeout=SEARCH_OVERALL_TIMEOUT)

            if genesys_user_id and genesys_data:
                # Direct user lookup
                genesys_result = genesys_data
                logger.info(f"Genesys fetch for specific user ID: {genesys_user_id}")
            elif genesys_data:
                if isinstance(genesys_data, dict):
                    if genesys_data.get("error") == "too_many_results":
                        genesys_error = genesys_data.get("message")
                        logger.info(
                            f"Genesys search for '{search_term}' - Too many results: {genesys_data.get('total')}"
                        )
                    elif genesys_data.get("multiple_results"):
                        genesys_multiple = True
                        genesys_result = genesys_data
                        logger.info(
                            f"Genesys search for '{search_term}' - Multiple results: {len(genesys_data.get('results', []))}"
                        )
                    else:
                        # Single result already processed
                        genesys_result = genesys_data
                        logger.info(
                            f"Genesys search for '{search_term}' - Found single user"
                        )
                else:
                    genesys_result = genesys_data
            else:
                logger.info(f"Genesys search for '{search_term}' - No results")

        except FutureTimeoutError:
            logger.error(
                f"Genesys search timed out after {SEARCH_OVERALL_TIMEOUT} seconds"
            )
            genesys_error = f"Genesys search timed out after {SEARCH_OVERALL_TIMEOUT} seconds. Please try a more specific search term."
            genesys_future.cancel()
        except TimeoutError as e:
            # Handle our custom TimeoutError from Genesys service
            logger.error(f"Genesys timeout: {str(e)}")
            genesys_error = str(e)
        except Exception as e:
            logger.error(f"Genesys search error: {str(e)}")
            genesys_error = "Genesys search encountered an error"

        # Get Graph API results with timeout
        try:
            graph_data = graph_future.result(timeout=SEARCH_OVERALL_TIMEOUT)

            if graph_user_id and graph_data:
                # Direct user lookup
                graph_result = graph_data
                logger.info(f"Graph API fetch for specific user ID: {graph_user_id}")
            elif graph_data:
                if isinstance(graph_data, dict) and graph_data.get("multiple_results"):
                    graph_multiple = True
                    graph_result = graph_data
                    logger.info(
                        f"Graph API search for '{search_term}' - Multiple results: {len(graph_data.get('results', []))}"
                    )
                else:
                    # Single result
                    graph_result = graph_data
                    logger.info(
                        f"Graph API search for '{search_term}' - Found single user"
                    )
            else:
                logger.info(f"Graph API search for '{search_term}' - No results")

        except FutureTimeoutError:
            logger.error(
                f"Graph API search timed out after {SEARCH_OVERALL_TIMEOUT} seconds"
            )
            graph_error = f"Microsoft Graph search timed out after {SEARCH_OVERALL_TIMEOUT} seconds. Please try a more specific search term."
            graph_future.cancel()
        except TimeoutError as e:
            # Handle our custom TimeoutError from Graph service
            logger.error(f"Graph API timeout: {str(e)}")
            graph_error = str(e)
        except Exception as e:
            logger.error(f"Graph API search error: {str(e)}")
            graph_error = "Microsoft Graph search encountered an error"

    # Check if all searches timed out
    if (
        ldap_error
        and genesys_error
        and graph_error
        and "timed out" in str(ldap_error)
        and "timed out" in str(genesys_error)
        and "timed out" in str(graph_error)
    ):
        return jsonify(
            {
                "error": "search_timeout",
                "message": f"Search timed out after {SEARCH_OVERALL_TIMEOUT} seconds. Please use a more specific search term.",
                "search_term": search_term,
            }
        ), 408  # Request Timeout

    # Merge LDAP and Graph results for Azure AD
    azure_ad_result = None
    azure_ad_error = None
    azure_ad_multiple = False

    # Handle single results - merge them (only when BOTH are single results)
    if (ldap_result and not ldap_multiple) and (graph_result and not graph_multiple):
        # Both are single results - direct merge
        azure_ad_result = merge_ldap_graph_data(ldap_result, graph_result)

    # Handle multiple results - need to match and merge
    elif ldap_multiple or graph_multiple:
        logger.info(
            f"Handling multiple results - LDAP multiple: {ldap_multiple}, Graph multiple: {graph_multiple}"
        )
        # Smart matching when we have single LDAP + multiple Graph results
        if (
            ldap_result
            and not ldap_multiple
            and graph_multiple
            and graph_result
            and graph_result.get("results")
        ):
            logger.info("Smart matching: Single LDAP + Multiple Graph results")
            # Try to match Graph results with the single LDAP result by email
            ldap_email = ldap_result.get("mail")
            if ldap_email:
                matched_graph = None
                for g_user in graph_result["results"]:
                    if g_user.get("mail", "").lower() == ldap_email.lower():
                        matched_graph = g_user
                        break

                if matched_graph:
                    # Found a match - get full Graph details for the matched user
                    graph_user_id = matched_graph.get("id")
                    if graph_user_id:
                        logger.info(
                            f"Fetching full Graph details for user ID: {graph_user_id}"
                        )
                        # Fetch full details for the matched user
                        full_graph_user = graph_service.get_user_by_id(graph_user_id)
                        if full_graph_user:
                            logger.info(
                                f"Full Graph user data fields: {list(full_graph_user.keys())}"
                            )
                            if "photoUrl" in full_graph_user:
                                logger.info("Graph photo URL present: Yes")
                            else:
                                logger.info("Graph photo URL present: No")
                            if "lastPasswordChangeDateTime" in full_graph_user:
                                logger.info(
                                    f"Password change date: {full_graph_user['lastPasswordChangeDateTime']}"
                                )
                            if "createdDateTime" in full_graph_user:
                                logger.info(
                                    f"Created date: {full_graph_user['createdDateTime']}"
                                )
                            azure_ad_result = merge_ldap_graph_data(
                                ldap_result, full_graph_user
                            )
                            logger.info(
                                f"Smart match: Found Graph user {matched_graph.get('displayName')} matching LDAP email {ldap_email}"
                            )
                            logger.info(
                                f"Merged result has Graph data: {azure_ad_result.get('hasGraphData', False)}"
                            )
                            logger.info(
                                f"Merged result has thumbnailPhoto: {'thumbnailPhoto' in azure_ad_result}"
                            )
                        else:
                            logger.warning(
                                f"Failed to fetch full Graph user details for ID: {graph_user_id}"
                            )
                            # Fallback to merging with basic data
                            azure_ad_result = merge_ldap_graph_data(
                                ldap_result, matched_graph
                            )
                    else:
                        logger.warning("No Graph user ID found in matched result")
                        # Fallback to merging with basic data
                        azure_ad_result = merge_ldap_graph_data(
                            ldap_result, matched_graph
                        )
                else:
                    # No match found, show multiple results
                    azure_ad_multiple = True
                    azure_ad_result = graph_result
            else:
                # No email to match, show multiple results
                azure_ad_multiple = True
                azure_ad_result = graph_result

        # Smart matching when we have multiple LDAP + single Graph result
        elif (
            ldap_multiple
            and ldap_result
            and ldap_result.get("results")
            and graph_result
            and not graph_multiple
        ):
            # Try to match LDAP results with the single Graph result by email
            graph_email = graph_result.get("mail")
            if graph_email:
                matched_ldap = None
                for l_user in ldap_result["results"]:
                    if l_user.get("mail", "").lower() == graph_email.lower():
                        matched_ldap = l_user
                        break

                if matched_ldap:
                    # Found a match - merge the matched LDAP with single Graph
                    azure_ad_result = merge_ldap_graph_data(matched_ldap, graph_result)
                    logger.info(
                        f"Smart match: Found LDAP user {matched_ldap.get('displayName')} matching Graph email {graph_email}"
                    )
                else:
                    # No match found, show multiple results
                    azure_ad_multiple = True
                    azure_ad_result = ldap_result
            else:
                # No email to match, show multiple results
                azure_ad_multiple = True
                azure_ad_result = ldap_result

        # Both have multiple results
        elif ldap_multiple and graph_multiple:
            azure_ad_multiple = True
            azure_ad_result = {
                "multiple_results": True,
                "ldap_results": ldap_result.get("results", []) if ldap_result else [],
                "graph_results": graph_result.get("results", [])
                if graph_result
                else [],
                "total": (ldap_result.get("total", 0) if ldap_result else 0)
                + (graph_result.get("total", 0) if graph_result else 0),
            }
        elif ldap_multiple:
            azure_ad_multiple = True
            azure_ad_result = ldap_result
        else:  # graph_multiple only
            azure_ad_multiple = True
            azure_ad_result = graph_result

    # Handle case where we have only one source (no results from the other)
    else:
        if ldap_result and not graph_result:
            azure_ad_result = merge_ldap_graph_data(ldap_result, None)
        elif graph_result and not ldap_result:
            azure_ad_result = merge_ldap_graph_data(None, graph_result)
        # else both are None, azure_ad_result remains None

    # Combine errors
    if ldap_error and graph_error:
        azure_ad_error = (
            "Both Active Directory and Microsoft Graph searches encountered errors"
        )
    elif ldap_error:
        azure_ad_error = ldap_error
    elif graph_error:
        azure_ad_error = graph_error

    # Smart matching: If we have single AD result and multiple Genesys results, try to match by email
    if (
        azure_ad_result
        and not azure_ad_multiple
        and genesys_multiple
        and genesys_result
        and genesys_result.get("results")
    ):
        # Get the email from the single AD result
        ad_email = azure_ad_result.get("mail")

        if ad_email:
            logger.info(
                f"Smart matching: Single AD result with email {ad_email}, checking {len(genesys_result['results'])} Genesys results"
            )

            # Look for a matching Genesys user by email
            matched_user = None
            for g_user in genesys_result["results"]:
                if g_user.get("email", "").lower() == ad_email.lower():
                    matched_user = g_user
                    logger.info(
                        f"Smart match found: Genesys user {g_user.get('name')} matches AD email {ad_email}"
                    )
                    break

            # If we found a match, get the full user details
            if matched_user and matched_user.get("id"):
                try:
                    full_genesys_user = genesys_service.get_user_by_id(
                        matched_user["id"]
                    )
                    if full_genesys_user:
                        genesys_result = full_genesys_user
                        genesys_multiple = False
                        logger.info(
                            f"Smart match successful: Retrieved full Genesys user details for {matched_user.get('name')}"
                        )
                except Exception as e:
                    logger.error(f"Error retrieving matched Genesys user: {str(e)}")

    # Audit logging
    services_used = []
    total_results = 0
    search_success = True
    error_messages = []

    # Track which services were used and results
    if ldap_result or ldap_error:
        services_used.append("LDAP")
        if ldap_result and not ldap_multiple:
            total_results += 1
        elif ldap_multiple and ldap_result.get("results"):
            total_results += len(ldap_result.get("results", []))
        if ldap_error:
            error_messages.append(f"LDAP: {ldap_error}")

    if graph_result or graph_error:
        services_used.append("Graph")
        if graph_result and not graph_multiple:
            total_results += 1
        elif graph_multiple and graph_result.get("results"):
            total_results += len(graph_result.get("results", []))
        if graph_error:
            error_messages.append(f"Graph: {graph_error}")

    if genesys_result or genesys_error:
        services_used.append("Genesys")
        if genesys_result and not genesys_multiple:
            total_results += 1
        elif genesys_multiple and genesys_result.get("results"):
            total_results += len(genesys_result.get("results", []))
        if genesys_error:
            error_messages.append(f"Genesys: {genesys_error}")

    # If all services failed, mark as unsuccessful
    if error_messages and len(error_messages) == len(services_used):
        search_success = False

    # Log the search
    try:
        from app.services.audit_service import audit_service

        audit_service.log_search(
            user_email=user_email,
            search_query=search_term,
            results_count=total_results,
            services=services_used,
            user_role=user_role,
            ip_address=user_ip,
            user_agent=user_agent,
            success=search_success,
            error_message="; ".join(error_messages) if error_messages else None,
            additional_data={
                "specific_user_requested": bool(
                    genesys_user_id or ldap_user_dn or graph_user_id
                ),
                "multiple_results": azure_ad_multiple or genesys_multiple,
                "timeout_occurred": any("timed out" in msg for msg in error_messages),
            },
        )
    except Exception as e:
        logger.error(f"Failed to log search audit: {str(e)}")

    return jsonify(
        {
            "azureAD": azure_ad_result,
            "azureAD_error": azure_ad_error,
            "azureAD_multiple": azure_ad_multiple,
            "genesys": genesys_result,
            "genesys_error": genesys_error,
            "genesys_multiple": genesys_multiple,
            "search_term": search_term,
        }
    )
