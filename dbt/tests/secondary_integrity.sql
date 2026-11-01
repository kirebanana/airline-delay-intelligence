-- Missing allocations are disclosed exclusions; malformed/negative or new complete
-- reconciliation failures block. Exceptions identify exact independently reviewed
-- source rows; see docs/baseline.md. No allocation or outcome value is rewritten.
select flight_key from {{ ref('fact_flights') }}
where category_eligible is distinct from (cancelled=0 and diverted=0 and arrival_delayed=1)
 or carrier_minutes is distinct from try_to_double(nullif("CarrierDelay",''))
 or weather_minutes is distinct from try_to_double(nullif("WeatherDelay",''))
 or nas_minutes is distinct from try_to_double(nullif("NASDelay",''))
 or security_minutes is distinct from try_to_double(nullif("SecurityDelay",''))
 or late_aircraft_minutes is distinct from try_to_double(nullif("LateAircraftDelay",''))
 or ("CarrierDelay"<>'' and not regexp_like("CarrierDelay",'[0-9]+([.][0-9]+)?'))
 or ("WeatherDelay"<>'' and not regexp_like("WeatherDelay",'[0-9]+([.][0-9]+)?'))
 or ("NASDelay"<>'' and not regexp_like("NASDelay",'[0-9]+([.][0-9]+)?'))
 or ("SecurityDelay"<>'' and not regexp_like("SecurityDelay",'[0-9]+([.][0-9]+)?'))
 or ("LateAircraftDelay"<>'' and not regexp_like("LateAircraftDelay",'[0-9]+([.][0-9]+)?'))
 or category_complete is distinct from (category_eligible and carrier_minutes is not null
    and weather_minutes is not null and nas_minutes is not null
    and security_minutes is not null and late_aircraft_minutes is not null)
 or reported_minutes is distinct from iff(category_complete,
    carrier_minutes+weather_minutes+nas_minutes+security_minutes+late_aircraft_minutes,null)
 or unallocated_minutes is distinct from iff(category_complete,arrival_delay-reported_minutes,null)
 or (category_complete and (arrival_delay is null or abs(unallocated_minutes)>0.000001)
     and not (("SOURCE_SHA256"='7a96466f2165b93ac1a064422c960e9b3089c2cc8a70c2cbabc8fde1c8b0af31'
          and "SOURCE_ROW_NUMBER"=432835
          and "SOURCE_ROW_SHA256"='6f5f8a19f8c3d65e1e0a064a5660985b4c13206709083c7cc41f7eefe6a9699c')
          or ("SOURCE_SHA256"='68c5a96d28c6193a85e7257ba131faf0112b810c54e3a9fc38ff61cb66b5bfa0'
          and "SOURCE_ROW_NUMBER"=416811
          and "SOURCE_ROW_SHA256"='276f51920a74634e164decea6802afb1176382e87e28c3d5429ef66daa98b849')
          or ("SOURCE_SHA256"='852dee3ba0dc7ab124440eac58056e27744f79a73ed2c92b3f59dae3eef12d2e'
          and "SOURCE_ROW_NUMBER"=370558
          and "SOURCE_ROW_SHA256"='0d92e0ae5bd4ee6a6e933924687f0fc9225ad80e3f4a2b7231282af78d276cfd')
          or ("SOURCE_SHA256"='60e14dd57856474a351b77935f9e004f05d43aaa37e2c0411f05a6a303c8f3ec'
          and "SOURCE_ROW_NUMBER"=382201
          and "SOURCE_ROW_SHA256"='54978dbd325a7721fe2fab430fc639cb1d462fc8f757880fea1fbee416bade34')
          or ("SOURCE_SHA256"='60e14dd57856474a351b77935f9e004f05d43aaa37e2c0411f05a6a303c8f3ec'
          and "SOURCE_ROW_NUMBER"=441145
          and "SOURCE_ROW_SHA256"='02fb9bb3d3c827cb2cda3d9277e392261521a6b5fc4adb4240b136d07deae8e6')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=521583
          and "SOURCE_ROW_SHA256"='cac6d219c21ba69c7886838d3da58a9c6d4c96c6b96afeada7f15532e416f76c')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=529535
          and "SOURCE_ROW_SHA256"='f3ff6d2639e1aa9a1300dbec849717c27064ce7562a87a1e4372cf0af381ea52')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=551098
          and "SOURCE_ROW_SHA256"='744dfde1f8e906a2f75b7a10be8ef6bece3a521d2d97b40f75aa4374c4873655')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=551665
          and "SOURCE_ROW_SHA256"='a0d1b239241b1a00b1831a9e22e1590d6951a8ed259820e36fd76c10fb2e05d4')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=553361
          and "SOURCE_ROW_SHA256"='9dc45dafcab985074b7ed63e512ca5ad044f390bb545796a5eb24795199a32d2')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=554832
          and "SOURCE_ROW_SHA256"='aa437b2f8026a9bff4485dc214eea800fc5b113284f9f877cf4d3305568cb82d')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=559464
          and "SOURCE_ROW_SHA256"='d2feab0679a71582dce33bcf472db9289ddb0ab17e577b2567551f8c61c5865d')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=563067
          and "SOURCE_ROW_SHA256"='65bf990f13ec387aa8b7e66c32efb43e8e0f47402e6e8a749be58311623eff3d')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=594240
          and "SOURCE_ROW_SHA256"='01c314e4c93a81a55df0e26715634da846220218cb1d3e716f43d54aee09eebb')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=597291
          and "SOURCE_ROW_SHA256"='37688f1f2c55ca2885e054cc7dfba3600f87d62e9213dfb790fb668a32d016bb')
          or ("SOURCE_SHA256"='858ba018a0f4bea73b140a4052586b492c3790300f5726851593ab3161d26eba'
          and "SOURCE_ROW_NUMBER"=599553
          and "SOURCE_ROW_SHA256"='fce2a6ba19295548df7661bd9764100b4018d4933076f7af5616bd23360b6650')))
 or recovery_eligible is distinct from
    (cancelled=0 and diverted=0 and departure_delay>=15 and arrival_delay is not null)
 or signed_improvement is distinct from iff(recovery_eligible,departure_delay-arrival_delay,null)
 or recovered_below_threshold is distinct from (recovery_eligible and arrival_delay<15)
 or recovery_band is distinct from
    (case when signed_improvement<0 then 'Worsened (<0)'
          when signed_improvement=0 then 'Unchanged (0)'
          when signed_improvement<15 then 'Improved (0–<15)'
          when signed_improvement<30 then 'Improved (15–<30)'
          when signed_improvement is not null then 'Improved (≥30)' end)
 or cancellation_reason is distinct from
    (case when cancelled=1 then case "CancellationCode"
          when 'A' then 'Carrier' when 'B' then 'Weather' when 'C' then 'NAS'
          when 'D' then 'Security' else 'Unknown / unrecognized' end end)
