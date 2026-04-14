package com.yahav.athleagent.model

data class AlertItem(
    val message: String,
    val iconRes: Int,
    val bgColorStr: String,
    val strokeColorStr: String,
    val textColorStr: String,
    val iconColorStr: String,
    val onClick: () -> Unit
)