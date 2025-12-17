package com.yahav.athleagent

import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textview.MaterialTextView
import com.yahav.athleagent.logic.LoginManager


private fun MainActivity.refreshUi() {
    TODO("Not yet implemented")
}

class MainActivity : AppCompatActivity() {


    private lateinit var googleSignInButton : MaterialButton

    private lateinit var editTextUsername : TextInputEditText

    private lateinit var editTextPassword : TextInputEditText

    private lateinit var loginButton : MaterialButton

    private lateinit var forgotPassword : MaterialTextView

    private lateinit var newAccountLink : MaterialTextView

    private lateinit var loginManager: LoginManager




    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)
        findViews()
       // loginManager = LoginManager()
        initViews()

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }
    }


    private fun findViews() {
        googleSignInButton = findViewById(R.id.GoogleSignInButton)
        editTextUsername = findViewById(R.id.editTextUsername)
        editTextPassword = findViewById(R.id.editTextPassword)
        loginButton = findViewById(R.id.loginButton)
        forgotPassword = findViewById(R.id.forgotPassword)
        newAccountLink = findViewById(R.id.newAccountLink)
    }

    private fun initViews() {
//        googleSignInButton.setOnClickListener {
//            loginManager.googleLogin()
//        }
        loginButton.setOnClickListener {
          //  loginManager.login()
//        }
//        forgotPassword.setOnClickListener {
//            loginManager.forgotPassword()
//        }
//        newAccountLink.setOnClickListener {
//            loginManager.createAccount()
//        }

//        text user name and password


            refreshUi()
        }


        fun refreshUi() {
            TODO()
        }
    }
}

