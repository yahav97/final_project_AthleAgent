# Full UI/UX Professional Upgrade Plan

This plan expands the high-end "Soft Layered" design to all Athlete and Coach features, Dashboards, and Home screens. We will maintain the original color palette while elevating the visual quality and interactive feel.

## Proposed Changes

### 1. Unified Design Language (Across All Screens)
- **Cards & Containers:** Update all `MaterialCardView` elements to have a 24dp-32dp corner radius and smooth elevations (4dp-8dp).
- **Backgrounds:** Use `background_white_alice_blue` consistently for main backgrounds.
- **Typography:** Standardize font sizes and weights using `roboto_bold` for headers and `roboto_regular` for body text.

### 2. Feature-Specific Upgrades
#### [activity_daily_check_in.xml](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/main/res/layout/activity_daily_check_in.xml)
- **Soft Form Containers:** Group survey sections into elevated cards instead of a flat vertical list.
- **Slider Styling:** Modernize the energy and stress sliders with custom thumb and track styling.
- **Button Consistency:** Use the refined gradient button style for the "Submit" action.

#### [activity_coach_dashboard.xml](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/main/res/layout/activity_coach_dashboard.xml) & [activity_athlete_dashboard.xml](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/main/res/layout/activity_athlete_dashboard.xml)
- **Glass-Effect Polish:** Refine the "Soft Layered" look for the risk score dials and charts.
- **Micro-animations:** Apply the `anim_auth_entrance` style animation to all dashboard widgets on entry.

#### [activity_home_athlete.xml](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/main/res/layout/activity_home_athlete.xml) & [activity_home_coach.xml](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/main/res/layout/activity_home_coach.xml)
- **Nav Card Overhaul:** Upgrade the large action cards (Daily Survey, Meal Analysis, etc.) to use better iconography and subtle shadows.
- **Entrance Sequence:** Ensure all dashboard elements slide in sequentially for a premium "loading" experience.

### 3. Smooth Transitions (Code Level)
- **Activity Animations:** Implement smooth cross-fades or slide transitions when navigating between features.
- **Interaction Feedback:** Add subtle scale-down effects to buttons when clicked.

## Verification Plan
- **XML Consistency Check:** Verify all modified screens use the unified corner radii and elevations.
- **Animation Smoothness:** Test the entrance animations in a local build environment.
- **Color Integrity:** Ensure no new colors were introduced; only existing palette used.
