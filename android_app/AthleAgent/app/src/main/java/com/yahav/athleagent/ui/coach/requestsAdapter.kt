package com.yahav.athleagent.ui.coach

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.widget.AppCompatImageButton
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.textview.MaterialTextView
import com.yahav.athleagent.R
import com.yahav.athleagent.model.AthleteRequest

// Adapter for displaying a list of pending athlete join requests in a RecyclerView
class RequestsAdapter(
    private val requestsList: List<AthleteRequest>,
    private val onApproveClick: (AthleteRequest) -> Unit,
    private val onRejectClick: (AthleteRequest) -> Unit
) : RecyclerView.Adapter<RequestsAdapter.RequestViewHolder>() {

    // ViewHolder class that holds references to the UI elements of a single request item
    class RequestViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val emailTxt: MaterialTextView = view.findViewById(R.id.itemRequest_LBL_email)
        val btnApprove: AppCompatImageButton = view.findViewById(R.id.itemRequest_BTN_approve)
        val btnReject: AppCompatImageButton = view.findViewById(R.id.itemRequest_BTN_reject)
    }

    // Inflates the XML layout for individual list items
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RequestViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_athlete_request, parent, false)
        return RequestViewHolder(view)
    }

    // Binds data to the UI elements and sets up button click listeners
    override fun onBindViewHolder(holder: RequestViewHolder, position: Int) {
        val request = requestsList[position]

        // Display the athlete's email
        holder.emailTxt.text = request.athleteEmail

        // Trigger the respective callback when an action button is clicked
        holder.btnApprove.setOnClickListener { onApproveClick(request) }
        holder.btnReject.setOnClickListener { onRejectClick(request) }
    }

    // Returns the total number of pending requests in the list
    override fun getItemCount(): Int = requestsList.size
}