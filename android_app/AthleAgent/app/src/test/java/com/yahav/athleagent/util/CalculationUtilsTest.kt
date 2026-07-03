package com.yahav.athleagent.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

class CalculationUtilsTest {

    @Test
    fun `getRiskLevel returns correct labels for score ranges`() {
        assertEquals("Low", CalculationUtils.getRiskLevel(10))
        assertEquals("Low", CalculationUtils.getRiskLevel(20))
        assertEquals("Medium", CalculationUtils.getRiskLevel(35))
        assertEquals("Medium", CalculationUtils.getRiskLevel(50))
        assertEquals("High", CalculationUtils.getRiskLevel(65))
        assertEquals("High", CalculationUtils.getRiskLevel(70))
        assertEquals("Critical", CalculationUtils.getRiskLevel(85))
    }

    @Test
    fun `formatDateToKey returns correct yyyy-MM-dd format`() {
        val calendar = Calendar.getInstance()
        calendar.set(2023, Calendar.OCTOBER, 25)
        val date = calendar.time
        
        assertEquals("2023-10-25", CalculationUtils.formatDateToKey(date))
    }

    @Test
    fun `isTeamCodeValid validates 6-character alphanumeric codes`() {
        assertTrue(CalculationUtils.isTeamCodeValid("ATHL23"))
        assertTrue(CalculationUtils.isTeamCodeValid("COACH1"))
        assertFalse(CalculationUtils.isTeamCodeValid("ATHL")) // Too short
        assertFalse(CalculationUtils.isTeamCodeValid("ATHL234")) // Too long
        assertFalse(CalculationUtils.isTeamCodeValid("athl23")) // Lowercase not allowed
        assertFalse(CalculationUtils.isTeamCodeValid("ATHL!#")) // Special chars not allowed
    }

    @Test
    fun `getSleepHours formats minutes to readable string`() {
        assertEquals("8h 0m", CalculationUtils.getSleepHours(480))
        assertEquals("7h 30m", CalculationUtils.getSleepHours(450))
        assertEquals("0h 45m", CalculationUtils.getSleepHours(45))
    }
}