package com.yahav.athleagent.ui.athlete

import android.util.TypedValue
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.textview.MaterialTextView
import com.yahav.athleagent.R
import com.yahav.athleagent.model.AthleteItem
import androidx.core.graphics.toColorInt

class AthleteAdapter(
    private val athletes: List<AthleteItem>,
    private val onAthleteClick: (AthleteItem) -> Unit
) : RecyclerView.Adapter<AthleteAdapter.AthleteViewHolder>() {

    // Stores the currently selected athlete's position (default: none selected)
    private var selectedPosition = RecyclerView.NO_POSITION

    class AthleteViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val nameTxt: MaterialTextView = view.findViewById(R.id.itemAthlete_TXT_name)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AthleteViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_athlete_name, parent, false)
        return AthleteViewHolder(view)
    }

    override fun onBindViewHolder(holder: AthleteViewHolder, position: Int) {
        val athlete = athletes[position]
        holder.nameTxt.text = athlete.name

        // Check if the current item is the selected one
        if (position == selectedPosition) {
            // Highlight the selected item with a subtle background color
            holder.nameTxt.setBackgroundColor("#E3EBF2".toColorInt())
        } else {
            // Restore the default transparent background with ripple effect for unselected items
            val typedValue = TypedValue()
            holder.itemView.context.theme.resolveAttribute(android.R.attr.selectableItemBackground, typedValue, true)
            holder.nameTxt.setBackgroundResource(typedValue.resourceId)
        }

        // Handle item click
        holder.itemView.setOnClickListener {
            // Save the previous position to un-highlight it
            val previousPosition = selectedPosition
            // Update to the newly selected position
            selectedPosition = holder.bindingAdapterPosition

            // Refresh only the two items that changed state (to save resources)
            notifyItemChanged(previousPosition)
            notifyItemChanged(selectedPosition)

            // Trigger the regular click action defined in the Activity
            onAthleteClick(athlete)
        }
    }

    override fun getItemCount() = athletes.size
}