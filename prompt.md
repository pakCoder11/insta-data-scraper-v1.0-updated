Tweets scraping function is successfully added .. 

I want to make some changes 

(1) When a backend function async def scrape_tweets_using_selenium(account_url,down_scroll_limit) , finished the execution it shows the modal message "Tweets scraping completed successfully, data is saved in Tweets_Data.xlsx and tweets_data.json " just goto View Data option and check the files ... , this modal display for some seocnds .. user can read the info perfectly ... 

(2) The task start dialog should be removed because it's annoying ... 

(3) logs are saved in logs.txt and also displayed on a logs option but when I am scraping tweets the logs aren't displayed on a console screen on main windows ... please check this I want to print the logs on a console screen on main windows also ...  

this is a code for displaying logs on a console screen on main windows also ...  
                write_logs_to_file("-------------------")
                for key, value in tweet_data.items():
                    write_logs_to_file(f"{key}: {value}")
                write_logs_to_file("-------------------") 

Please do these changes with tweets scraping function , keep in mind the rest of the code is working fine ... don't edit in such way which disturb the other code ... 

Thanks


