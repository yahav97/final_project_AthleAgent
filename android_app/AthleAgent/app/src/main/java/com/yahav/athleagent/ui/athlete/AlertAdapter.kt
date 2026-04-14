package com.yahav.athleagent.ui.athlete

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.graphics.toColorInt
import androidx.recyclerview.widget.RecyclerView
import com.yahav.athleagent.databinding.ItemAlertCardBinding
import com.yahav.athleagent.model.AlertItem

class AlertsAdapter(private val alerts: List<AlertItem>) :
    RecyclerView.Adapter<AlertsAdapter.AlertViewHolder>() {

    inner class AlertViewHolder(val itemBinding: ItemAlertCardBinding) :
        RecyclerView.ViewHolder(itemBinding.root)

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AlertViewHolder {
        val itemBinding = ItemAlertCardBinding.inflate(
            LayoutInflater.from(parent.context), parent, false
        )
        return AlertViewHolder(itemBinding)
    }

    override fun onBindViewHolder(holder: AlertViewHolder, position: Int) {
        val alert = alerts[position]

        holder.itemBinding.alertCardRoot.setCardBackgroundColor(alert.bgColorStr.toColorInt())
        holder.itemBinding.alertCardRoot.strokeColor = alert.strokeColorStr.toColorInt()
        holder.itemBinding.alertText.text = alert.message
        holder.itemBinding.alertText.setTextColor(alert.textColorStr.toColorInt())
        holder.itemBinding.alertIcon.setImageResource(alert.iconRes)
        holder.itemBinding.alertIcon.setColorFilter(alert.iconColorStr.toColorInt())

        holder.itemBinding.alertCardRoot.setOnClickListener {
            alert.onClick()
        }
    }

    override fun getItemCount() = alerts.size
}