

---------- Column Info ------------


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'orders'


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'sellers'


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'products'


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'order_items'


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'order_reviews'


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'order_payments'


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'customers'


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'product_category_name_translation'


select COLUMN_NAME,DATA_TYPE from INFORMATION_SCHEMA.columns
where TABLE_NAME = 'geolocation'


-----------------------------------------------


---------------------------------------------------------------------------- Customers table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

--Count of missing values

select SUM(case when customer_id IS null then 1 else 0 end) as missing_cust_id,
		SUM(case when customer_unique_id is null then 1 else 0 end) as missing_cust_uni_id,
		sum(case when customer_zip_code_prefix IS null then 1 else 0 end) as missing_zip_prefix, 
		sum(case when customer_city is null then 1 else 0 end) as missing_cust_city,
		sum(case when customer_state is null then 1 else 0 end) as missing_cust_state from customers


-- Duplicates 
select customer_id from customers
group by customer_id
having COUNT(*) > 1

select customer_unique_id from customers
group by customer_unique_id
having COUNT(*) > 1
----------------------------

-- Total customers and unique customers

select count(customer_id) tot_cust_id, COUNT(distinct customer_unique_id) tot_uni_cust from customers

-- city wise customer count

select customer_city, COUNT(distinct customer_id)as cust_count
from Customers
group by customer_city
order by COUNT(*) desc

-- invalid zip prefix

select count(*) as short_zip from customers                                                
where  customer_zip_code_prefix < 10000


---------------------------------------------------------------------------- Order items table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

-- Count of missing values

select sum(case when order_id is null then 1 else 0 end) as missing_order_id,
		sum(case when order_item_id is null then 1 else 0 end) as missing_order_item_id,
		sum(case when product_id is null then 1 else 0 end) as missing_product_id,
		sum(case when seller_id is null then 1 else 0 end) as missing_seller_id,
		sum(case when shipping_limit_date is null then 1 else 0 end) as missing_shipping_limit_date,
		sum(case when price is null then 1 else 0 end) as missing_price,
		sum(case when freight_value is null then 1 else 0 end) as missing_freight_value from order_items


------------------------------------

-- Checking if order_id is having duplicates

select order_id, COUNT(*) counts from order_items
group by order_id
having COUNT(*) > 1

------------------------------------

-- checking uniqueness in order_id and order_items_id

select count(order_id) as tot_rwos, COUNT(distinct order_id) uni_ord_id from order_items

-------------------------------------

-- Checking if Price and Freight is having negative values

select price, freight_value from order_items
where price <= 0 or freight_value < 0

---------------------------------------------------------------------------- Products table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

-- checking for the  missing values

select  sum(case when product_id is null then 1 else 0 end) as missing_product_id,
		sum(case when product_category_name is null then 1 else 0 end) as missing_product_category_name,
		sum(case when product_name_lenght is null then 1 else 0 end) as missing_product_name_length,
		sum(case when product_description_lenght is null then 1 else 0 end) as missing_product_description_length,
		sum(case when product_photos_qty is null then 1 else 0 end) as missing_products_photos_qty,
		sum(case when product_weight_g is null then 1 else 0 end) as missing_product_weight_g,
		sum(case when product_length_cm is null then 1 else 0 end) as missing_product_length_cm,
		sum(case when product_height_cm is null then 1 else 0 end) as missing_product_height_cm,
		sum(case when product_width_cm is null then 1 else 0 end) as missing_product_width_cm from products

--------------------------------------------
-- Expanding the null values

select * from products
where product_category_name is null
				-- total of 610 product_id does not have product_category_name and other descriptions

---------------------------------------------

-- checking for duplicates

select product_id ,product_category_name , product_photos_qty , product_description_lenght,COUNT(*) from products 
group by product_id , product_category_name , product_photos_qty , product_description_lenght
having COUNT(*) > 1

----------------------------------------------

-- products having no translations in translations table
select distinct p.product_category_name from products p
left join product_category_name_translation t on p.product_category_name = t.product_category_name
where p.product_category_name is not null and t.product_category_name is null

---------------------------------------------

-- Checking weight and size  zero or less than zero and negative
select sum(case when product_weight_g <= 0 then 1 else 0 end) as bad_weight,     
       sum(case when product_length_cm <= 0 then 1 else 0 end) as bad_length,    
       sum(case when product_height_cm <= 0 then 1 else 0 end) as bad_height,    
       sum(case when product_width_cm <= 0 then 1 else 0 end) as bad_width       
from products			-- it will not affect the analysis


---------------------------------------------------------------------------- Sellers table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


-- Checking for the missing values

select sum(case when seller_id is null then 1 else 0 end) as missing_seller_id,
		sum(case when seller_zip_code_prefix is null then 1 else 0 end) as missingseller_zip_code_prefix,
		sum(case when seller_city is null then 1 else 0 end) as missing_seller_city,
		sum(case when seller_state is null then 1 else 0 end) as missing_seller_state from sellers

-----------------------------------------

-- Checking duplicates

select seller_id, COUNT(seller_id) from sellers
group by seller_id
having COUNT(seller_id) > 1

----------------------------------------

-- sellers with no items sold

select count(*) as sellers_without_sales from  sellers s                                                  
left join order_items i on s.seller_id = i.seller_id            
where i.seller_id is null

-----------------------------------------

-- state wise seller distribution

select  seller_state, COUNT(*) as total_rows from sellers                                                   
group by seller_state                                          
order by total_rows desc

---------------------------------------------------------------------------- Order reviews table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

-- Checking for the missing values

select sum(case when review_id is null then 1 else 0 end) as missing_review_id,
		sum(case when order_id is null then 1 else 0 end) as missing_order_id,
		sum(case when review_score is null then 1 else 0 end) as missing_review_score,
		sum(case when review_comment_title is null then 1 else 0 end) as missing_review_comm_title,
		sum(case when review_comment_message is null then 1 else 0 end) as missing_review_comm_message,
		sum(case when review_creation_date is null then 1 else 0 end) as missing_creation_date,
		sum(case when review_answer_timestamp is null then 1 else 0 end) as missing_review_answer_timestamp from order_reviews

-- Checking for the duplicates


select review_id ,COUNT(*) as counts from order_reviews -- with review id
group by review_id
having COUNT(*) > 1

select * from order_reviews
where review_id in (select review_id from order_reviews -- Checking for the records which are having those duplicate review ids 
					group by review_id					-- We are having 1603 duplicate rows with different review_id for the same order_id
					having COUNT(*) > 1)

select * from order_reviews
where review_id = '28642ce6250b94cc72bc85960aec6c62'

select COUNT(distinct review_id) from order_reviews


-- Checking for the inconsistent data

select * from order_reviews
where review_score > 5 or review_score < 1


---------------------------------------------------------------------------- Product category names translation table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

-- check for missings

select * from product_category_name_translation
where product_category_name is null or product_category_name_english is null

-- checking for duplicates

select product_category_name , product_category_name_English , COUNT(*) as counts from product_category_name_translation
group by product_category_name , product_category_name_English
HAVING COUNT(*) > 1

-- checking the uniqueness of prod_cat_name

select COUNT(*) tot_rows, COUNT(distinct product_category_name) unique_names from product_category_name_translation




---------------------------------------------------------------------------- Orders table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

-- Missing values

select sum(case when order_id is null then 1 else 0 end) as missing_order_id,
		sum(case when customer_id is null then 1 else 0 end) as missing_customer_id,
		sum(case when order_status is null then 1 else 0 end) as missing_order_status,
		sum(case when order_purchase_timestamp is null then 1 else 0 end) as missing_order_purchase_timestamp,
		sum(case when order_approved_at is null then 1 else 0 end) as missing_order_approved_at,
		sum(case when order_delivered_carrier_date is null then 1 else 0 end) as missing_order_delivered_carrier_date,
		sum(case when order_delivered_customer_date is null then 1 else 0 end) as missing_order_delivered_customer_date,
		sum(case when order_estimated_delivery_date is null then 1 else 0 end) as missing_order_estimated_delivery_date from orders

---------------------------------------------------

-- Checking for the duplicates

select order_id , COUNT(*) from orders 
group by order_id
having COUNT(*) > 1 

--------------------------------------------------

-- Expanding the null values

select * from orders
where order_approved_at is null or order_delivered_carrier_date is null or order_delivered_customer_date is null

-------------------------------------------------

--That record which are prsent in customer tables
select count(*) as orphan_orders from orders as o
left join Customers as c on o.customer_id = c.customer_id
where c.customer_id is null 

-------------------------------------------------

-- Further expensions

select * from orders
where order_status = 'canceled' 
				-- Its normal to have nulls values in dates when the order is canceledd

select * from orders
where order_status = 'shipped'
				-- if the Delivery status 'shipped' then it is expected to have order_delivered_customer_date as null 

select * from orders
where order_status = 'unavailable'

select * from orders
where order_status = 'processing'

----------------------------------------------------

-- Order delivered to customer date before approved date

select * from orders
where order_approved_at > order_delivered_customer_date
			-- 61 rows are having delivery before approval 
select * from orders
where order_approved_at is null and order_status = 'delivered'

			-- 14 rows are having delivery but approval is null

			-- checking if the payment actually happen or not
			select * from order_items
			where order_id = 'e04abd8149ef81b95221e88f6ed9ab6a'
			
			select * from order_payments
			where order_id = 'e04abd8149ef81b95221e88f6ed9ab6a'

select  *  from orders 
where order_delivered_customer_date is null and order_status = 'delivered'

select  *  from orders 
where order_delivered_customer_date is not null and order_status != 'delivered'

---------------------------------------------------------------------------- Geolocation table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

--Checking for Missing values

select sum(case when geolocation_zip_code_prefix is null then 1 else 0 end) as missing_geolocation_zip_code,
		sum(case when geolocation_lat is null then 1 else 0 end) as missing_geolocation_lat,
		sum(case when geolocation_lng is null then 1 else 0 end) as missing_geolocation_lng,
		sum(case when geolocation_city is null then 1 else 0 end) as missing_geolocation_city,
		sum(case when geolocation_state is null then 1 else 0 end) as missing_geolocation_state from geolocation

----------------------------------------------

-- Checking for the Duplicates

select geolocation_zip_code_prefix, geolocation_lng, geolocation_lat, geolocation_city,geolocation_state, COUNT(*) counts from geolocation
group by geolocation_zip_code_prefix, geolocation_lng, geolocation_lat, geolocation_city,geolocation_state
having COUNT(*) > 1

-- we'll remove the 128270 duplicates from the geolocations

-- checking on 1 zip code prefix
-- Data inconsistency in geolocation, because of the minor changes in longitute and latitude
select * from geolocation
where geolocation_zip_code_prefix = 1037

------------------------------------------------

-- checking How many zip codes have more than 1 different coordinate
select count(*) as zips_with_multiple_coords
from (
    select geolocation_zip_code_prefix
    from geolocation
    group by geolocation_zip_code_prefix
    having count(distinct concat(geolocation_lat, '|', geolocation_lng)) > 1
) t

-------------------------------------------------

-- total unique zip code prefix
select COUNT(distinct geolocation_zip_code_prefix) tot_zip_codes from geolocation

-------------------------------------------------

-- customer zip that not present in geolocation
select count(distinct c.customer_zip_code_prefix) as zip_not_in_geolocation from Customers c
left join geolocation g on c.customer_zip_code_prefix = g.geolocation_zip_code_prefix
where g.geolocation_zip_code_prefix is null

-------------------------------------------------

select  right ('00000' + cast(geolocation_zip_code_prefix as varchar(5)), 5) from geolocation

alter table GEOLOCATION
alter column geolocation_lat float

update geolocation
set geolocation_zip_code_prefix = right('00000' + cast(geolocation_zip_code_prefix as varchar(5)), 5)
from geolocation


---------------------------------------------------------------------------- Order payment table -------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


-- Checking for the missing values

select SUM(case when order_id IS null then 1 else 0 end) as missing_ord_ids, sum(case when payment_sequential is null then 1 else 0 end) as missing_payment_sequential,
		sum(case when payment_type is null then 1 else 0 end) as mssing_payment_type,
		sum(case when payment_installments is null then 1 else 0 end) as missing_payment_installments,
		sum(case when payment_value is null then 1 else 0 end) as missing_payment_value from order_payments

-- Checking for the duplicates

select order_id, COUNT(*) as counts from order_payments
group by order_id
having COUNT(*) > 1

-- further, inconsistency check

select * from order_payments
where order_id in (select order_id from order_payments 
					group by order_id
					having COUNT(*)> 1)

-- analysis on the basis of payments type

select payment_type,count(*) as payment_rows, count(distinct order_id) as total_orders, sum(payment_value) as total_payment_value
from order_payments
group by payment_type
order by total_payment_value desc

select order_id ,COUNT(*) [count of order]
from order_payments
where payment_type = 'voucher'
group by order_id
having COUNT(*) > 1
order by [count of order] desc

select * from order_payments
where order_id = 'fa65dad1b0e818e3ccc5cb0e39231352'
order by payment_sequential asc

----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------- End of Data Auditing ----------------------------------------------------------------------------------------


----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
-------------------------------------------------------------------- Data cleaning -----------------------------------------------------------------------------------------------

----------------------------------- Orders payments table

select * from order_payments

select order_id,
		COUNT(*) as counts,
       sum(payment_value) as total_payment_value
from order_payments
group by order_id
order by order_id


select order_id,COUNT(*) tot_ord, max(payment_installments) tot_installment, SUM(case when payment_type = 'credit_card' then payment_value else 0 end) as credit_card_amt,
					sum(case when payment_type = 'boleto' then payment_value else 0 end) as boleto_amt,
					sum(case when payment_type = 'voucher' then payment_value else 0 end) as voucher_amt, 
					sum(case when payment_type = 'debit_card' then payment_value else 0 end) as debit_card_amt ,
					sum(payment_value) tot_amt into order_payments_op from order_payments
group by order_id

select * from order_payments_op


---------------------------------- Orders table

select * from orders


select order_id, customer_id, order_status, order_purchase_timestamp,order_approved_at,
		order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date, 
		case when order_approved_at > order_delivered_customer_date then 'deliver_before_approve' 
			when order_status = 'delivered' and order_approved_at IS null then 'missing_approval' 
			else 'clean' end as data_quality_flag 
			into orders_o from orders


select data_quality_flag, COUNT(*) counts from orders_o
group by data_quality_flag

--------------------------------- geolocations table

;with distinct_geo as  (
select distinct geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state from geolocation),

ranked as (select *,ROW_NUMBER() over (partition by geolocation_zip_code_prefix order by geolocation_lat) as rows_num from distinct_geo)
select geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state into geolocations_gl from ranked
where rows_num = 1

select * from geolocations_gl

select COUNT(distinct geolocation_zip_code_prefix) as unique_zip_codes from geolocations_gl


--------------------------------- Order revieews table

select * from order_reviews

-- removing the duplicate review_ids for the same order_id
select review_id, order_id, review_score, review_comment_title, review_comment_message, review_creation_date, review_answer_timestamp 
		into order_reviews_or from (select *, ROW_NUMBER() over(PARTITION by review_id order by review_creation_date desc, review_answer_timestamp desc) row_num from order_reviews) as ranks
where row_num = 1

select * from order_reviews_or


-----------------------------------Products table

-- creating cleaned products table with English category and quality flag
select p.product_id, case when c.product_category_name_english is not null then c.product_category_name_english else p.product_category_name end as product_category_name_english,
    p.product_name_lenght, p.product_description_lenght, p.product_photos_qty, p.product_weight_g, p.product_length_cm, p.product_height_cm, p.product_width_cm,
    case when p.product_category_name is null then 'missing_category'
        when p.product_weight_g is null or p.product_length_cm is null or p.product_height_cm is null or p.product_width_cm is null then 'missing_dimensions' else 'clean'
		end as data_quality_flag
		into products_p from products p
left join product_category_name_translation c
    on p.product_category_name = c.product_category_name

















































