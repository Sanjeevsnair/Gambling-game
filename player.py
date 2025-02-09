import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import pandas as pd
import hashlib
from urllib.parse import parse_qs
import time

# Firebase Configuration
cred = credentials.Certificate("gambling-game-exodia-game-firebase-adminsdk-fbsvc-8f08c488a4.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://gambling-game-exodia-game-default-rtdb.firebaseio.com/"
    })
    
    
# Initialize Firebase references
timer_ref = db.reference("timers")

# Check if place bet timer is running
timer_data = timer_ref.get()
is_placebet_timer_running = timer_data.get("is_placebet_timer_running", False)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_session_state():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'bet_placed' not in st.session_state:
        st.session_state.bet_placed = False

def verify_password(player_id, password):
    players_ref = db.reference("players")
    player_data = players_ref.child(player_id).get()
    return player_data and player_data.get('password_hash') == hash_password(password)

def request_loan(requester_id, requester_name, amount):
    loans_ref = db.reference("loan_requests")
    loans_ref.child(requester_id).set({
        "requester_name": requester_name,
        "amount": amount,
        "status": "pending",
        "timestamp": time.time()
    })

def check_active_loans(player_id):
    active_loans_ref = db.reference("active_loans")
    loans = active_loans_ref.get() or {}
    return {k: v for k, v in loans.items() 
            if v['borrower_id'] == player_id or v['lender_id'] == player_id}

def process_loan_settlement(winning_player_id):
    active_loans_ref = db.reference("active_loans")
    scores_ref = db.reference("scores")
    loans = active_loans_ref.get() or {}
    
    for loan_id, loan in loans.items():
        if loan['borrower_id'] == winning_player_id:
            # Winner has to pay back 50% of loan
            payback_amount = loan['amount'] * 0.5
            
            # Update borrower's score
            borrower_score = scores_ref.child(loan['borrower_id']).get()
            scores_ref.child(loan['borrower_id']).set(borrower_score - payback_amount)
            
            # Update lender's score
            lender_score = scores_ref.child(loan['lender_id']).get()
            scores_ref.child(loan['lender_id']).set(lender_score + payback_amount)
            
            # Mark loan as settled
            active_loans_ref.child(loan_id).update({
                'status': 'settled',
                'settlement_date': time.time()
            })
        else:
            # Borrower lost, pay additional 10 points penalty
            penalty_amount = loan['amount'] + 10
            
            # Update borrower's score
            borrower_score = scores_ref.child(loan['borrower_id']).get()
            scores_ref.child(loan['borrower_id']).set(borrower_score - penalty_amount)
            
            # Update lender's score
            lender_score = scores_ref.child(loan['lender_id']).get()
            scores_ref.child(loan['lender_id']).set(lender_score + penalty_amount)
            
            # Mark loan as settled with penalty
            active_loans_ref.child(loan_id).update({
                'status': 'settled_with_penalty',
                'settlement_date': time.time()
            })
            


# Get URL parameters
query_params = st.query_params
player_name = query_params['player_name']
player_id = query_params['player_number']


if not player_name or not player_id:
    st.error("⚠️ Invalid URL. Please use the correct URL.")
    st.stop()

# Initialize session state
init_session_state()

st.subheader("🎲 Player Betting Lobby")
st.write(f"Welcome, {player_name} (ID: {player_id})")


# Registration/Login Section if not authenticated
if not st.session_state.authenticated:
    with st.form("setup_form"):
        st.write("First time? Register. Already registered? Login.")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password (Already registered, Skip this part)", type="password")
        submitted = st.form_submit_button("Register/Login")
        
        if submitted:
            players_ref = db.reference("players")
            player_data = players_ref.child(player_id).get()
            
            if player_data:  # Login flow
                if verify_password(player_id, password):
                    st.session_state.authenticated = True
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid password!")
            else:  # Registration flow
                if password != confirm_password:
                    st.error("Passwords don't match!")
                else:
                    players_ref.child(player_id).set({
                        'name': player_name,
                        'password_hash': hash_password(password),
                        'created_at': time.time()
                    })
                    scores_ref = db.reference("scores")
                    scores_ref.child(player_id).set(50)  # Initial score
                    st.session_state.authenticated = True
                    st.success("Registration successful!")
                    st.rerun()

else:
    # Display All Player Scores (Read-only)
    # Display All Player Scores (Read-only)
    st.sidebar.header("👥 All Player Scores")
    try:
        scores_ref = db.reference("scores")
        scores_data = scores_ref.get()
    
        # Convert the list to a dictionary if needed
        if isinstance(scores_data, list):
            scores = {str(i): score for i, score in enumerate(scores_data) if score is not None}
        else:
            scores = scores_data if isinstance(scores_data, dict) else {}
    
        # Create DataFrame
        scores_df = pd.DataFrame(list(scores.items()), columns=["Player", "Score"])
        st.sidebar.table(scores_df)
    
        # Get player score safely
        player_score = scores.get(player_id, 50)
    
    except Exception as e:
        st.error(f"Error fetching scores: {str(e)}")
        scores_df = pd.DataFrame(columns=["Player", "Score"])
        player_score = 50  # Default score

    # Player's betting interface
    player_score = scores.get(player_id, 50)
    st.info(f"💰 Your Current Score: {player_score} points")

    # Betting Form
    with st.form("betting_form"):
        chosen_number = st.number_input(
            "Choose a number (1-10):", 
            min_value=1, 
            max_value=10, 
            key="chosen_number"
        )
    
        bet_amount = st.number_input(
            "Enter Bet Amount (Min: 10 points):", 
            min_value=10, 
            max_value=int(player_score),  # Ensure max_value is int
            key="bet_amount"
        )
    
        confirm_password = st.text_input(
            "Confirm your password to place bet:", 
            type="password",
            help="Enter your password to confirm bet placement"
        )
    
        st.write("By clicking 'Place Bet', you confirm that:")
        st.write(f"- You are {player_name} (ID: {player_id})")
    
        # Add a submit button
        submit_button = st.form_submit_button("Place Bet")
        st.session_state.bet_placed = False
        if is_placebet_timer_running:
            st.success("✅ You can place your bet now.")
            # Add your betting form here
            if submit_button:
                if not verify_password(player_id, confirm_password):
                    st.error("❌ Invalid password! Bet not placed.")
                elif st.session_state.bet_placed:
                    st.warning("⚠️ You have already placed a bet for this round!")
                else:
                    try:
                        # Place bet
                        updated_score = player_score - bet_amount
                        scores_ref.child(player_id).set(updated_score)
                
                        bet_ref = db.reference(f"bets/{player_id}")
                        bet_ref.set({
                            "chosen_number": chosen_number,
                            "bet_amount": bet_amount,
                            "timestamp": time.time(),
                            "player_name": player_name
                        })
                
                        st.session_state.bet_placed = True
                        st.success(f"✅ Bet placed successfully! Remaining Balance: {updated_score} points")
            
                    except Exception as e:
                        st.error(f"❌ Error placing bet: {str(e)}")
        else:
            st.warning("⛔ You cannot place bets right now.")
        

    # Show real-time results
    st.markdown("<h4 class='smaller-header'>📊 Game Results</h4>",unsafe_allow_html = True) 
    
    try:
        winning_number = db.reference("winning_number").get()
        if winning_number:
            st.success(f"🎯 Winning Number: {winning_number}")
            updated_scores = scores_ref.get()
            if updated_scores and player_id in updated_scores:
                st.info(f"💰 Your Updated Score: {updated_scores[player_id]} points")
                st.session_state.bet_placed = False
    except Exception as e:
        st.error(f"❌ Error fetching results: {str(e)}")
        
    # Loan Management Section
    st.markdown("<h4 class='smaller-header'>💰 Loan Management</h4>",unsafe_allow_html = True) 
    
    
    # Check player's current loans
    active_loans = check_active_loans(player_id)
    if active_loans:
        st.warning("⚠️ You have active loans:")
        for loan_id, loan in active_loans.items():
            if loan['borrower_id'] == player_id:
                st.write(f"You borrowed {loan['amount']} points from {loan['lender_name']}")
            else:
                st.write(f"You lent {loan['amount']} points to {loan['borrower_name']}")
    
    # Request Loan Tab
    if st.checkbox("Request New Loan"):
        with st.form("loan_request_form"):
            loan_amount = st.number_input("Loan Amount", min_value=10, max_value=50)
            st.write("Note: If you win, 50% will be paid back. If you lose, loan amount + 10 points penalty.")
            request_submitted = st.form_submit_button("Submit Loan Request")
            
            if request_submitted:
                if len(active_loans) > 0:
                    st.error("❌ You already have an active loan!")
                else:
                    request_loan(player_id, player_name, loan_amount)
                    st.success("✅ Loan request submitted successfully!")
    
    # View Available Loan Requests
    st.markdown("<h4 class='smaller-header'>📥 Available Loan Requests</h4>", unsafe_allow_html=True)

    loan_requests_ref = db.reference("loan_requests")
    loan_requests = loan_requests_ref.get()

    # Check if loan_requests is a list or dictionary
    if isinstance(loan_requests, list):
        # Convert list to dictionary if needed
        loan_requests_dict = {str(i): request for i, request in enumerate(loan_requests) if isinstance(request, dict)}
    elif isinstance(loan_requests, dict):
        loan_requests_dict = loan_requests
    else:
        loan_requests_dict = {}

    # Process loan requests
    for req_id, request in loan_requests_dict.items():
        if request['status'] == 'pending' and req_id != player_id:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"Player: {request['requester_name']}")
                st.write(f"Amount: {request['amount']} points")
            with col2:
                if st.button(f"Give Loan to {request['requester_name']}", key=f"loan_{req_id}"):
                    # Process loan giving
                    scores_ref = db.reference("scores")
                    lender_score = scores_ref.child(player_id).get()
                
                    if lender_score >= request['amount']:
                        # Deduct from lender
                        scores_ref.child(player_id).set(lender_score - request['amount'])
                    
                        # Add to borrower
                        borrower_score = scores_ref.child(req_id).get()
                        scores_ref.child(req_id).set(borrower_score + request['amount'])
                    
                        # Create active loan record
                        active_loans_ref = db.reference("active_loans")
                        loan_id = f"loan_{int(time.time())}"
                        active_loans_ref.child(loan_id).set({
                            "borrower_id": req_id,
                            "borrower_name": request['requester_name'],
                            "lender_id": player_id,
                            "lender_name": player_name,
                            "amount": request['amount'],
                            "status": "active",
                            "timestamp": time.time()
                        })
                    
                        # Remove loan request
                        loan_requests_ref.child(req_id).delete()
                    
                        st.success("✅ Loan given successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Insufficient points to give loan!")

    
    # Logout option
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.bet_placed = False
        st.rerun()